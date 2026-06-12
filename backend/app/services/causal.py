from datetime import UTC, datetime
from socket import gethostname
from pathlib import Path
from uuid import uuid4

import networkx as nx
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.algorithms.causal import run_algorithm, write_edges_csv
from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.analysis import AnalysisJob
from app.models.dataset import DatasetVersion
from app.models.user import User
from app.schemas.causal import BackgroundEdge, CausalEdge, CausalJobCreate, CausalJobResult, EffectRequest, EffectResponse
from app.services.serialization import job_read


def _version_for_user(db: Session, version_id: str, user: User) -> DatasetVersion:
    version = db.scalar(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset))
        .where(DatasetVersion.id == version_id)
    )
    if not version or version.dataset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据版本不存在")
    return version


def _job_for_user(db: Session, job_id: str, user: User) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if not job or job.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分析任务不存在")
    return job


def create_job(
    db: Session,
    settings: Settings,
    user: User,
    payload: CausalJobCreate,
    background_tasks: BackgroundTasks,
):
    version = _version_for_user(db, payload.dataset_version_id, user)
    available = {column["name"] for column in version.columns_json}
    missing = [column for column in payload.selected_variables if column not in available]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"字段不存在: {', '.join(missing)}")

    job = AnalysisJob(
        owner_id=user.id,
        dataset_version_id=version.id,
        algorithm=payload.algorithm,
        selected_variables_json=payload.selected_variables,
        background_edges_json=[edge.model_dump() for edge in payload.background_edges],
        algorithm_params_json=payload.algorithm_params,
        status="pending",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_job, settings, job.id)
    return job_read(job)


def run_job(settings: Settings, job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return
        version = db.get(DatasetVersion, job.dataset_version_id)
        if not version:
            job.status = "failed"
            job.progress = 100
            job.error_message = "数据版本不存在"
            job.finished_at = datetime.now(UTC)
            db.commit()
            return

        if job.status == "canceled":
            return
        job.status = "running"
        job.progress = 10
        job.started_at = datetime.now(UTC)
        job.worker_id = f"{gethostname()}:{job_id[:8]}"
        db.commit()
        edges = run_algorithm(
            job.algorithm,
            version.storage_path,
            list(job.selected_variables_json or []),
            [BackgroundEdge(**edge) for edge in job.background_edges_json or []],
            dict(job.algorithm_params_json or {}),
        )
        db.refresh(job)
        if job.status == "canceled":
            return
        job.progress = 80
        db.commit()
        result_dir = Path(settings.storage_root) / "users" / job.owner_id / "jobs" / job.id
        result_dir.mkdir(parents=True, exist_ok=True)
        result_path = result_dir / f"{job.algorithm}_{uuid4()}.csv"
        write_edges_csv(result_path, edges)

        job.result_edges_json = [edge.model_dump() for edge in edges]
        job.result_path = str(result_path)
        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        job.error_message = None
        db.commit()
    except Exception as exc:
        job = db.get(AnalysisJob, job_id)
        if job:
            job.status = "failed"
            job.progress = 100
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def get_job(db: Session, user: User, job_id: str):
    return job_read(_job_for_user(db, job_id, user))


def list_jobs(db: Session, user: User, dataset_version_id: str | None = None):
    query = select(AnalysisJob).where(AnalysisJob.owner_id == user.id).order_by(AnalysisJob.created_at.desc())
    if dataset_version_id:
        query = query.where(AnalysisJob.dataset_version_id == dataset_version_id)
    return [job_read(job) for job in db.scalars(query).all()]


def retry_job(
    db: Session,
    settings: Settings,
    user: User,
    job_id: str,
    background_tasks: BackgroundTasks,
):
    job = _job_for_user(db, job_id, user)
    if job.status not in {"failed", "canceled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有失败或已取消任务可以重试")
    job.status = "pending"
    job.progress = 0
    job.started_at = None
    job.finished_at = None
    job.worker_id = None
    job.error_message = None
    job.result_edges_json = None
    job.result_path = None
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_job, settings, job.id)
    return job_read(job)


def cancel_job(db: Session, user: User, job_id: str):
    job = _job_for_user(db, job_id, user)
    if job.status in {"completed", "failed", "canceled"}:
        return job_read(job)
    job.status = "canceled"
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    job.error_message = "任务已取消"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_read(job)


def get_job_result(db: Session, user: User, job_id: str) -> CausalJobResult:
    job = _job_for_user(db, job_id, user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    edges = [CausalEdge(**edge) for edge in job.result_edges_json or []]
    nodes = sorted(
        set(job.selected_variables_json or [])
        | {edge.node1 for edge in edges}
        | {edge.node2 for edge in edges}
    )
    return CausalJobResult(job=job_read(job), edges=edges, nodes=nodes)


def calculate_effect(db: Session, user: User, payload: EffectRequest) -> EffectResponse:
    job = _job_for_user(db, payload.job_id, user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    edges = [CausalEdge(**edge) for edge in job.result_edges_json or []]
    graph = nx.DiGraph()
    graph.add_edges_from((edge.node1, edge.node2) for edge in edges)
    if not nx.is_directed_acyclic_graph(graph):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图中存在环，无法计算因果效应")
    if payload.cause_var not in graph or payload.effect_var not in graph:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择图中的变量")

    version = db.get(DatasetVersion, job.dataset_version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据版本不存在")

    try:
        from EI.calculator import EffectiveInformation

        calculator = EffectiveInformation(version.storage_path, graph)
        if not calculator.set_var(payload.cause_var, payload.effect_var):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="因果路径不存在")
        effects = calculator.measure_causal_effect()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return EffectResponse(
        kl_divergence=float(effects[0]),
        js_divergence=float(effects[1]),
        total_variation=float(effects[2]),
        wasserstein_distance=float(effects[3]),
        hellinger_distance=float(effects[4]),
    )
