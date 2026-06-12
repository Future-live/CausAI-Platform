import json
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.security import clear_auth_cookies, decode_token, set_auth_cookies
from app.db.session import get_db
from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset, DatasetVersion
from app.models.favorite import FavoriteItem
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin
from app.schemas.causal import BackgroundEdge, EffectRequest
from app.schemas.dataset import (
    ChartDataRequest,
    ColumnVisibilityRequest,
    FilterRequest,
    PrepareRequest,
    QuantileFilter,
    ValueFilter,
)
from app.services.auth import authenticate_user, register_user
from app.services.causal import calculate_effect, get_job_result, run_job
from app.services.dataframe import read_dataframe, records
from app.services.datasets import (
    create_dataset,
    create_filtered_version,
    create_prepared_version,
    get_chart_data,
    get_column_distribution,
    get_column_values,
    get_statistics,
    list_datasets,
    update_column_visibility,
)

APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
router = APIRouter()


def _json_error(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "message": message}, status_code=code)


def _auth_user_from_request(request: Request, db: Session, settings: Settings) -> User | None:
    token = request.cookies.get(settings.access_cookie_name)
    if not token:
        return None
    try:
        user_id = decode_token(token, "access", settings)
    except HTTPException:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def _require_user(request: Request, db: Session, settings: Settings) -> User:
    user = _auth_user_from_request(request, db, settings)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def _page_user(request: Request, db: Session, settings: Settings) -> User | RedirectResponse:
    user = _auth_user_from_request(request, db, settings)
    return user or RedirectResponse("/", status_code=303)


def _render(request: Request, template_name: str, **context: Any):
    def legacy_url_for(name: str, **path_params: Any) -> str:
        if name == "static":
            filename = str(path_params.get("filename") or path_params.get("path") or "").lstrip("/")
            return f"/static/{filename}"
        return str(request.url_for(name, **path_params))

    context.setdefault("session", request.session)
    context["url_for"] = legacy_url_for
    return templates.TemplateResponse(template_name, {"request": request, **context})


def _latest_version(dataset: Dataset) -> DatasetVersion | None:
    if not dataset.versions:
        return None
    dataset.versions.sort(key=lambda version: version.created_at)
    return dataset.versions[-1]


def _remember_dataset(request: Request, dataset: Dataset) -> None:
    version = _latest_version(dataset)
    request.session["dataset_id"] = dataset.id
    request.session["version_id"] = version.id if version else None
    request.session["uploaded_filename"] = dataset.original_filename


def _current_dataset_version(request: Request, db: Session, user: User) -> tuple[Dataset | None, DatasetVersion | None]:
    dataset_id = request.session.get("dataset_id")
    version_id = request.session.get("version_id")
    if dataset_id:
        dataset = db.scalar(
            select(Dataset)
            .options(selectinload(Dataset.versions))
            .where(Dataset.id == dataset_id, Dataset.owner_id == user.id)
        )
        if dataset:
            if version_id:
                version = next((item for item in dataset.versions if item.id == version_id), None)
                if version:
                    return dataset, version
            version = _latest_version(dataset)
            if version:
                request.session["version_id"] = version.id
            return dataset, version

    dataset = db.scalar(
        select(Dataset)
        .options(selectinload(Dataset.versions))
        .where(Dataset.owner_id == user.id)
        .order_by(Dataset.created_at.desc())
    )
    if dataset:
        _remember_dataset(request, dataset)
        return dataset, _latest_version(dataset)
    request.session.setdefault("uploaded_filename", "dataset.csv")
    return None, None


def _profiles_for_template(version: DatasetVersion | None, db: Session, user: User) -> dict[str, Any]:
    if not version:
        return {"columns": [], "column_types": {}, "analysis_types": {}, "unique_values": {}}

    columns = [column["name"] for column in version.columns_json]
    column_types = {}
    analysis_types = {}
    unique_values = {}
    for column in version.columns_json:
        name = column["name"]
        semantic_type = column.get("semantic_type") or "text"
        analysis_type = column.get("analysis_type")
        column_types[name] = "numeric" if analysis_type == "measure" else semantic_type
        analysis_types[name] = "度量" if analysis_type == "measure" else "维度"
        if analysis_type != "measure":
            unique_values[name] = get_column_values(db, user, version.id, name, 1000).values
    return {
        "columns": columns,
        "column_types": column_types,
        "analysis_types": analysis_types,
        "unique_values": unique_values,
    }


def _current_dataframe(request: Request, db: Session, user: User) -> tuple[DatasetVersion, pd.DataFrame]:
    _, version = _current_dataset_version(request, db, user)
    if not version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传或选择数据文件")
    return version, read_dataframe(version.storage_path)


@router.get("/", name="log_in")
def log_in(request: Request):
    return _render(request, "log-in.html")


@router.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    payload = await request.json()
    try:
        user = authenticate_user(db, UserLogin(**payload))
    except HTTPException as exc:
        return _json_error(str(exc.detail), exc.status_code)
    set_auth_cookies(response, user.id, settings)
    return {"success": True, "message": "登录成功", "redirect_url": "/index.html", "auth_method": "local"}


@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    try:
        register_user(db, UserCreate(**payload))
    except Exception as exc:
        return _json_error(getattr(exc, "detail", str(exc)), getattr(exc, "status_code", 400))
    return {"success": True, "message": "注册成功，请登录"}


@router.get("/logout")
def logout(response: Response, settings: Settings = Depends(get_settings)):
    redirect = RedirectResponse("/", status_code=303)
    clear_auth_cookies(redirect, settings)
    return redirect


@router.get("/logout.html")
def legacy_logout(settings: Settings = Depends(get_settings)):
    redirect = RedirectResponse("/", status_code=303)
    clear_auth_cookies(redirect, settings)
    return redirect


@router.get("/profile.html")
def legacy_profile(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    dataset_count = len(list_datasets(db, user))
    job_count = len(db.scalars(select(AnalysisJob).where(AnalysisJob.owner_id == user.id)).all())
    favorite_count = len(db.scalars(select(FavoriteItem).where(FavoriteItem.owner_id == user.id)).all())
    return _render(
        request,
        "profile.html",
        user=user,
        dataset_count=dataset_count,
        job_count=job_count,
        favorite_count=favorite_count,
    )


@router.get("/index.html", name="index")
def index(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    return _render(request, "index.html", user=user)


@router.api_route("/data-upload.html", methods=["GET", "POST"], name="upload_file")
async def upload_file(
    request: Request,
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    if request.method == "GET":
        return _render(request, "data-upload.html", user=user)
    if not file:
        return _json_error("没有文件被上传")
    dataset = create_dataset(db, settings, user, file)
    _remember_dataset(request, dataset)
    return {"success": True, "message": "文件上传成功", "redirect_url": "/data-preparation.html"}


@router.api_route("/data-preparation.html", methods=["GET", "POST"], name="data_preparation")
async def data_preparation(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    message = ""
    dataset, version = _current_dataset_version(request, db, user)

    if request.method == "POST" and version:
        form = await request.form()
        action = form.get("action")
        try:
            if action == "prepare_data":
                fill_na = str(form.get("fill_na") or "None")
                payload = PrepareRequest(fill_na="none" if fill_na == "None" else fill_na, drop_na=form.get("drop_na") == "on")
                new_version = create_prepared_version(db, settings, user, version.id, payload)
                request.session["version_id"] = new_version.id
                message = "数据准备成功！"
            elif action == "global_filter_data":
                payload = FilterRequest(
                    global_low=float(form.get("global_quantile_low", 0)),
                    global_high=float(form.get("global_quantile_high", 1)),
                )
                new_version = create_filtered_version(db, settings, user, version.id, payload)
                request.session["version_id"] = new_version.id
                message = "全局数据筛选成功！"
            elif action == "filter_data_column":
                column = str(form.get("filter_column") or "")
                profile = next((item for item in version.columns_json if item["name"] == column), None)
                if profile and profile.get("analysis_type") == "measure":
                    payload = FilterRequest(
                        quantile_filters=[
                            QuantileFilter(
                                column=column,
                                low=float(form.get(f"quantile_low_{column}", 0)),
                                high=float(form.get(f"quantile_high_{column}", 1)),
                            )
                        ]
                    )
                else:
                    payload = FilterRequest(value_filters=[ValueFilter(column=column, values=list(form.getlist(f"selected_values_{column}")))])
                new_version = create_filtered_version(db, settings, user, version.id, payload)
                request.session["version_id"] = new_version.id
                message = f"{column} 列数据筛选成功！"
        except Exception as exc:
            message = f"处理失败：{getattr(exc, 'detail', str(exc))}"
        dataset, version = _current_dataset_version(request, db, user)

    context = _profiles_for_template(version, db, user)
    return _render(request, "data-preparation.html", message=message, user=user, **context)


@router.get("/statistical-analysis.html")
def statistical_analysis(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    dataset, version = _current_dataset_version(request, db, user)
    columns = [column["name"] for column in version.columns_json if column.get("enabled", True)] if version else []
    return _render(
        request,
        "statistical-analysis.html",
        columns=columns,
        user=user,
        dataset_id=dataset.id if dataset else "",
        version_id=version.id if version else "",
    )


@router.api_route("/causal-analysis.html", methods=["GET", "POST"])
async def causal_analysis_view(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    _, version = _current_dataset_version(request, db, user)
    if request.method == "GET":
        return _render(request, "causal-analysis.html", user=user)
    if not version:
        return JSONResponse({"error": "请先上传数据"}, status_code=400)
    form = await request.form()
    algorithm = str(form.get("algorithm") or "pc")
    selected = [item for item in str(form.get("sel_var") or "").split(",") if item]
    try:
        raw_edges = json.loads(str(form.get("background_edge") or "[]"))
    except json.JSONDecodeError:
        return JSONResponse({"error": "背景知识边格式错误"}, status_code=400)
    if not isinstance(raw_edges, list):
        return JSONResponse({"error": "背景知识边格式错误"}, status_code=400)
    background_edges = [
        BackgroundEdge(source=edge.get("source") or edge.get("from"), target=edge.get("target") or edge.get("to")).model_dump()
        for edge in raw_edges
        if isinstance(edge, dict) and (edge.get("source") or edge.get("from")) and (edge.get("target") or edge.get("to"))
    ]
    if len(selected) < 2:
        return JSONResponse({"error": "请至少选择两个变量"}, status_code=400)
    job = AnalysisJob(
        owner_id=user.id,
        dataset_version_id=version.id,
        algorithm=algorithm,
        selected_variables_json=selected,
        background_edges_json=background_edges,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    request.session["job_id"] = job.id
    request.session["selected_var"] = ",".join(selected)
    run_job(settings, job.id)
    return {"completed": True, "job_id": job.id}


@router.get("/big-model-analysis.html")
def big_model_analysis(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    return _render(request, "big-model-analysis.html", user=user)


@router.get("/favorites.html")
def favorites(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _page_user(request, db, settings)
    if isinstance(user, RedirectResponse):
        return user
    return _render(request, "favorites.html", user=user)


@router.get("/api/favorites")
def list_favorites(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    items = db.scalars(
        select(FavoriteItem)
        .where(FavoriteItem.owner_id == user.id)
        .order_by(FavoriteItem.created_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "kind": item.kind,
            "title": item.title,
            "description": item.description,
            "dataset_id": item.dataset_id,
            "group_name": item.group_name,
            "sort_order": item.sort_order,
            "payload": item.payload_json,
            "snapshot": item.snapshot_json,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@router.post("/api/favorites")
async def create_favorite(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    payload = await request.json()
    title = str(payload.get("title") or "").strip()
    kind = str(payload.get("kind") or "note").strip()
    if not title:
        return _json_error("收藏标题不能为空")
    dataset, _ = _current_dataset_version(request, db, user)
    payload_json = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    snapshot_json = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    try:
        sort_order = int(payload.get("sort_order") or 0)
    except (TypeError, ValueError):
        sort_order = 0
    item = FavoriteItem(
        owner_id=user.id,
        kind=kind[:40],
        title=title[:160],
        description=str(payload.get("description") or "").strip() or None,
        dataset_id=payload.get("dataset_id") or (dataset.id if dataset else None),
        group_name=str(payload.get("group_name") or "").strip() or None,
        sort_order=sort_order,
        payload_json=payload_json,
        snapshot_json=snapshot_json or payload_json,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "success": True,
        "id": item.id,
        "message": "已加入收藏夹",
    }


@router.delete("/api/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = _require_user(request, db, settings)
    item = db.get(FavoriteItem, favorite_id)
    if not item or item.owner_id != user.id:
        return _json_error("收藏不存在", 404)
    db.delete(item)
    db.commit()
    return {"success": True}


@router.get("/api/check-upload-status")
def check_upload_status(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, version = _current_dataset_version(request, db, user)
    return {"fileUploaded": bool(version)}


@router.get("/api/upload-history")
def upload_history(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    return [
        {
            "id": item.id,
            "dataset_id": item.id,
            "latest_version_id": item.latest_version_id,
            "filename": item.original_filename,
            "upload_time": item.created_at,
            "rows": item.row_count,
            "columns": item.column_count,
        }
        for item in list_datasets(db, user)
    ]


@router.post("/set_session")
async def set_session(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    payload = await request.json()
    dataset_id = payload.get("dataset_id")
    filename = payload.get("filename")
    query = select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.owner_id == user.id)
    if dataset_id:
        query = query.where(Dataset.id == dataset_id)
    elif filename:
        query = query.where(Dataset.original_filename == filename).order_by(Dataset.created_at.desc())
    dataset = db.scalar(query)
    if not dataset:
        return {"success": False, "message": "No filename provided"}
    _remember_dataset(request, dataset)
    return {"success": True}


@router.get("/api/plot-data")
def plot_data(column: str, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, version = _current_dataset_version(request, db, user)
    if not version:
        return JSONResponse({"error": "Data file not found in session."}, status_code=400)
    distribution = get_column_distribution(db, user, version.id, column)
    return {"labels": distribution.labels, "values": distribution.values}


@router.post("/update_use_column")
async def update_use_column(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    payload = await request.json()
    _, version = _current_dataset_version(request, db, user)
    if not version:
        return {"success": False, "message": "No active dataset"}
    column = payload.get("column")
    enabled = bool(payload.get("use"))
    enabled_columns = [item["name"] for item in version.columns_json if item.get("enabled", True)]
    if enabled and column not in enabled_columns:
        enabled_columns.append(column)
    if not enabled:
        enabled_columns = [item for item in enabled_columns if item != column]
    update_column_visibility(db, user, version.id, ColumnVisibilityRequest(enabled_columns=enabled_columns))
    return {"success": True}


@router.get("/api/get-data")
def get_data(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, df = _current_dataframe(request, db, user)
    return records(df.head(20000))


@router.get("/api/get-statistics")
def get_statistics_legacy(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, version = _current_dataset_version(request, db, user)
    if not version:
        return []
    return [item.model_dump() for item in get_statistics(db, user, version.id)]


@router.get("/api/get-var")
def get_var(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    selected = set(str(request.session.get("selected_var") or "").split(","))
    stats = get_statistics_legacy(request, db, settings)
    return [item for item in stats if not selected or item["name"] in selected]


@router.post("/api/generate-chart")
async def generate_chart(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, version = _current_dataset_version(request, db, user)
    if not version:
        return JSONResponse({"error": "Data file not found"}, status_code=400)
    payload = await request.json()
    try:
        chart_data = get_chart_data(
            db,
            user,
            version.id,
            ChartDataRequest(
                chart_type=payload.get("chartType") or payload.get("chart_type") or "scatter",
                x=payload.get("x"),
                y=payload.get("y"),
                color=payload.get("color"),
                size=payload.get("size"),
                opacity=payload.get("opacity"),
            ),
        )
    except HTTPException as exc:
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)
    return {
        "plot_data": chart_data.rows,
        "x_axis": chart_data.x_axis,
        "y_axis": chart_data.y_axis,
        "color": chart_data.color,
        "size": chart_data.size,
        "opacity": chart_data.opacity,
    }


@router.get("/check-analysis-status")
def check_analysis_status(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    job_id = request.session.get("job_id")
    if not job_id:
        return {"completed": False}
    job = db.get(AnalysisJob, job_id)
    return {"completed": bool(job and job.owner_id == user.id and job.status == "completed")}


@router.get("/get-csv-data")
def get_csv_data(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    job_id = request.session.get("job_id")
    if not job_id:
        return JSONResponse({"error": "结果文件未找到"}, status_code=404)
    result = get_job_result(db, user, job_id)
    csv_data = [
        {"Node1": edge.node1, "Node2": edge.node2, "Endpoint1": edge.endpoint1, "Endpoint2": edge.endpoint2}
        for edge in result.edges
    ]
    edges = [{"source": edge.node1, "target": edge.node2} for edge in result.edges]
    return {"csv_data": csv_data, "nodes": result.nodes, "edges": edges}


@router.get("/get_csv_data_new")
def get_csv_data_new(
    request: Request,
    format: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    data = get_csv_data(request, db, settings)
    if isinstance(data, JSONResponse):
        return data
    rows = data["csv_data"]
    if format == "csv":
        if not rows:
            return PlainTextResponse("")
        df = pd.DataFrame(rows)
        return PlainTextResponse(df.to_csv(index=False), media_type="text/csv")
    return rows


@router.post("/api/backdoor_adjustment")
async def backdoor_adjustment(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _require_user(request, db, settings)
    payload = await request.json()
    cause = payload.get("cause_var")
    effect = payload.get("effect_var")
    graph = nx.DiGraph()
    graph.add_nodes_from(payload.get("nodes") or [])
    graph.add_edges_from((edge.get("source"), edge.get("target")) for edge in payload.get("edges") or [])
    parents = set(graph.predecessors(effect)) if effect in graph else set()
    adjustment = sorted(item for item in parents if item != cause)
    return {"adjustment_set": adjustment, "configured": False}


@router.post("/api/calculate-effect")
async def calculate_effect_legacy(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    payload = await request.json()
    job_id = request.session.get("job_id")
    if not job_id:
        return JSONResponse({"error": "请先完成因果分析"}, status_code=400)
    return calculate_effect(db, user, EffectRequest(job_id=job_id, cause_var=payload["cause_var"], effect_var=payload["effect_var"])).model_dump()


@router.post("/api/analyze-causal-results")
async def analyze_causal_results(request: Request):
    payload = await request.json()
    causal_data = payload.get("causal_data", "")
    lines = [line for line in causal_data.splitlines() if line.strip()]
    return {
        "success": True,
        "analysis": f"当前未配置大模型密钥，已保留语义分析入口。检测到 {max(len(lines) - 1, 0)} 条因果边，可继续查看图结构与效应指标。",
    }


@router.post("/api/chat")
async def chat_handler():
    return {"success": False, "message": "语义聊天需要配置 DEEPSEEK_API_KEY"}


@router.get("/uploads/{filename}")
def download_file(filename: str, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    dataset = db.scalar(select(Dataset).where(Dataset.owner_id == user.id, Dataset.original_filename == filename).order_by(Dataset.created_at.desc()))
    if not dataset:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(dataset.storage_path, filename=dataset.original_filename)


@router.get("/download/{filename}", name="download")
def download(filename: str, request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _require_user(request, db, settings)
    _, version = _current_dataset_version(request, db, user)
    if not version:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(version.storage_path, filename=filename)
