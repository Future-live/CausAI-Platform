from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from werkzeug.utils import secure_filename

from app.core.config import Settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User
from app.schemas.dataset import (
    ChartDataRequest,
    ChartDataResponse,
    ColumnDistribution,
    ColumnValues,
    ColumnVisibilityRequest,
    DatasetListItem,
    FilterRequest,
    PrepareRequest,
    StatisticItem,
)
from app.services.dataframe import (
    SUPPORTED_DATASET_EXTENSIONS,
    is_supported_dataset_file,
    profile_columns,
    read_dataframe,
    records,
)
from app.services.serialization import dataset_read, version_read


def _user_storage(settings: Settings, user_id: str) -> Path:
    path = settings.storage_root / "users" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_path(settings: Settings, user_id: str, filename: str) -> tuple[str, Path]:
    safe = secure_filename(filename) or "dataset.csv"
    if not is_supported_dataset_file(safe):
        supported = ", ".join(sorted(SUPPORTED_DATASET_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型。当前支持: {supported}",
        )
    dataset_dir = _user_storage(settings, user_id) / "datasets" / str(uuid4())
    dataset_dir.mkdir(parents=True, exist_ok=True)
    return safe, dataset_dir / f"original_{safe}"


def _check_version_owner(db: Session, version_id: str, user: User) -> DatasetVersion:
    version = db.scalar(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset))
        .where(DatasetVersion.id == version_id)
    )
    if not version or version.dataset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据版本不存在")
    return version


def _enabled_columns(version: DatasetVersion) -> set[str]:
    return {col["name"] for col in version.columns_json if col.get("enabled", True)}


def create_dataset(db: Session, settings: Settings, user: User, upload: UploadFile) -> Dataset:
    filename = upload.filename or "dataset.csv"
    safe_name, destination = _safe_upload_path(settings, user.id, filename)

    bytes_written = 0
    with destination.open("wb") as buffer:
        while chunk := upload.file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > settings.max_upload_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件过大")
            buffer.write(chunk)

    try:
        df = read_dataframe(destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据文件解析失败: {exc}") from exc

    columns = profile_columns(df)
    dataset = Dataset(
        owner_id=user.id,
        original_filename=safe_name,
        storage_path=str(destination),
        row_count=len(df),
        column_count=len(df.columns),
        columns_json=columns,
    )
    db.add(dataset)
    db.flush()
    db.add(
        DatasetVersion(
            dataset_id=dataset.id,
            kind="original",
            storage_path=str(destination),
            operations_json=[{"type": "upload", "filename": safe_name}],
            row_count=len(df),
            columns_json=columns,
        )
    )
    db.commit()
    return get_dataset(db, user, dataset.id)


def list_datasets(db: Session, user: User) -> list[DatasetListItem]:
    datasets = db.scalars(
        select(Dataset)
        .options(selectinload(Dataset.versions))
        .where(Dataset.owner_id == user.id)
        .order_by(Dataset.created_at.desc())
    ).all()
    items: list[DatasetListItem] = []
    for dataset in datasets:
        latest = max(dataset.versions, key=lambda version: version.created_at) if dataset.versions else None
        items.append(
            DatasetListItem(
                id=dataset.id,
                original_filename=dataset.original_filename,
                row_count=dataset.row_count,
                column_count=dataset.column_count,
                created_at=dataset.created_at.isoformat(),
                latest_version_id=latest.id if latest else None,
            )
        )
    return items


def get_dataset(db: Session, user: User, dataset_id: str) -> Dataset:
    dataset = db.scalar(
        select(Dataset)
        .options(selectinload(Dataset.versions))
        .where(Dataset.id == dataset_id, Dataset.owner_id == user.id)
    )
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
    dataset.versions.sort(key=lambda version: version.created_at)
    return dataset


def get_dataset_read(db: Session, user: User, dataset_id: str):
    return dataset_read(get_dataset(db, user, dataset_id))


def get_rows(db: Session, user: User, version_id: str, limit: int, offset: int):
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    total = len(df)
    return {
        "rows": records(df.iloc[offset : offset + limit]),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def create_prepared_version(
    db: Session,
    settings: Settings,
    user: User,
    version_id: str,
    payload: PrepareRequest,
):
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    operations: list[dict] = []

    if payload.drop_na:
        before = len(df)
        df = df.dropna()
        operations.append({"type": "drop_na", "removed_rows": before - len(df)})

    if payload.fill_na != "none":
        numeric_columns = df.select_dtypes(include="number").columns
        non_numeric_columns = [column for column in df.columns if column not in numeric_columns]
        if payload.fill_na in {"mean", "median"}:
            values = getattr(df[numeric_columns], payload.fill_na)()
            df[numeric_columns] = df[numeric_columns].fillna(values)
            for column in non_numeric_columns:
                mode = df[column].mode(dropna=True)
                if not mode.empty:
                    df[column] = df[column].fillna(mode.iloc[0])
        elif payload.fill_na == "mode":
            for column in df.columns:
                mode = df[column].mode(dropna=True)
                if not mode.empty:
                    df[column] = df[column].fillna(mode.iloc[0])
        operations.append({"type": "fill_na", "method": payload.fill_na})

    enabled = _enabled_columns(version)
    columns = profile_columns(df, enabled)
    output_path = (
        _user_storage(settings, user.id)
        / "datasets"
        / version.dataset_id
        / f"prepared_{uuid4()}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    new_version = DatasetVersion(
        dataset_id=version.dataset_id,
        kind="prepared",
        storage_path=str(output_path),
        operations_json=[*version.operations_json, *operations],
        row_count=len(df),
        columns_json=columns,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return version_read(new_version)


def create_filtered_version(
    db: Session,
    settings: Settings,
    user: User,
    version_id: str,
    payload: FilterRequest,
):
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    enabled = _enabled_columns(version)
    operations: list[dict] = []

    if payload.global_low is not None and payload.global_high is not None:
        for column in df.select_dtypes(include="number").columns:
            low_value = df[column].quantile(payload.global_low)
            high_value = df[column].quantile(payload.global_high)
            df = df[(df[column] >= low_value) & (df[column] <= high_value)]
        operations.append({"type": "global_quantile", "low": payload.global_low, "high": payload.global_high})

    for item in payload.quantile_filters:
        if item.column not in df.columns or not pd.api.types.is_numeric_dtype(df[item.column]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{item.column} 不是数值列")
        low_value = df[item.column].quantile(item.low)
        high_value = df[item.column].quantile(item.high)
        df = df[(df[item.column] >= low_value) & (df[item.column] <= high_value)]
        operations.append({"type": "quantile", "column": item.column, "low": item.low, "high": item.high})

    for item in payload.value_filters:
        if item.column not in df.columns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{item.column} 不存在")
        values = item.values
        if pd.api.types.is_numeric_dtype(df[item.column]):
            values = pd.to_numeric(pd.Series(values), errors="coerce").dropna().tolist()
        df = df[df[item.column].isin(values)]
        operations.append({"type": "values", "column": item.column, "values": item.values})

    output_path = (
        _user_storage(settings, user.id)
        / "datasets"
        / version.dataset_id
        / f"filtered_{uuid4()}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    new_version = DatasetVersion(
        dataset_id=version.dataset_id,
        kind="filtered",
        storage_path=str(output_path),
        operations_json=[*version.operations_json, *operations],
        row_count=len(df),
        columns_json=profile_columns(df, enabled),
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return version_read(new_version)


def update_column_visibility(
    db: Session,
    user: User,
    version_id: str,
    payload: ColumnVisibilityRequest,
):
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    missing = set(payload.enabled_columns) - set(df.columns)
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"字段不存在: {', '.join(missing)}")
    version.columns_json = profile_columns(df, set(payload.enabled_columns))
    db.add(version)
    db.commit()
    db.refresh(version)
    return version_read(version)


def get_statistics(db: Session, user: User, version_id: str) -> list[StatisticItem]:
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    enabled = _enabled_columns(version)
    stats: list[StatisticItem] = []
    for column in df.columns:
        if column not in enabled:
            continue
        series = df[column]
        if pd.api.types.is_numeric_dtype(series):
            stats.append(
                StatisticItem(
                    name=column,
                    type="numerical",
                    mean=float(series.mean()) if not series.dropna().empty else None,
                    stdDev=float(series.std()) if len(series.dropna()) > 1 else None,
                    median=float(series.median()) if not series.dropna().empty else None,
                    missing=int(series.isna().sum()),
                    unique=int(series.nunique(dropna=True)),
                )
            )
        else:
            stats.append(
                StatisticItem(
                    name=column,
                    type="categorical",
                    missing=int(series.isna().sum()),
                    unique=int(series.nunique(dropna=True)),
                )
            )
    return stats


def get_chart_data(db: Session, user: User, version_id: str, payload: ChartDataRequest) -> ChartDataResponse:
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    selected = [payload.x, payload.y, payload.color, payload.size, payload.opacity]
    columns = [column for column in selected if column]
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"字段不存在: {', '.join(missing)}")
    if payload.chart_type in {"scatter", "line", "bar", "boxplot"} and (not payload.x or not payload.y):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择 X 轴和 Y 轴")
    subset = df[columns].head(payload.limit) if columns else df.head(payload.limit)
    return ChartDataResponse(
        rows=records(subset),
        x_axis=payload.x,
        y_axis=payload.y,
        color=payload.color,
        size=payload.size,
        opacity=payload.opacity,
    )


def get_column_distribution(db: Session, user: User, version_id: str, column: str) -> ColumnDistribution:
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    if column not in df.columns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字段不存在")
    series = df[column].dropna()
    if series.empty:
        return ColumnDistribution(column=column, kind="categories", labels=[], values=[])
    if pd.api.types.is_numeric_dtype(series):
        bins = min(12, max(4, int(series.nunique() ** 0.5)))
        counts = pd.cut(series, bins=bins, duplicates="drop").value_counts().sort_index()
        return ColumnDistribution(
            column=column,
            kind="histogram",
            labels=[str(label) for label in counts.index],
            values=[float(value) for value in counts.values],
        )
    counts = series.astype(str).value_counts().head(16)
    return ColumnDistribution(
        column=column,
        kind="categories",
        labels=[str(label) for label in counts.index],
        values=[float(value) for value in counts.values],
    )


def get_column_values(db: Session, user: User, version_id: str, column: str, limit: int = 500) -> ColumnValues:
    version = _check_version_owner(db, version_id, user)
    df = read_dataframe(version.storage_path)
    if column not in df.columns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字段不存在")
    values = df[column].dropna().drop_duplicates().head(limit).tolist()
    return ColumnValues(column=column, values=values)
