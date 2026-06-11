from datetime import datetime

from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset, DatasetVersion
from app.schemas.causal import BackgroundEdge, CausalJobRead
from app.schemas.dataset import ColumnProfile, DatasetRead, DatasetVersionRead


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def column_profiles(raw: list[dict]) -> list[ColumnProfile]:
    return [ColumnProfile(**item) for item in raw]


def version_read(version: DatasetVersion) -> DatasetVersionRead:
    return DatasetVersionRead(
        id=version.id,
        dataset_id=version.dataset_id,
        kind=version.kind,
        row_count=version.row_count,
        columns=column_profiles(version.columns_json),
        created_at=iso(version.created_at) or "",
    )


def dataset_read(dataset: Dataset) -> DatasetRead:
    latest = dataset.versions[-1] if dataset.versions else None
    return DatasetRead(
        id=dataset.id,
        original_filename=dataset.original_filename,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=column_profiles(dataset.columns_json),
        latest_version=version_read(latest) if latest else None,
        created_at=iso(dataset.created_at) or "",
    )


def job_read(job: AnalysisJob) -> CausalJobRead:
    return CausalJobRead(
        id=job.id,
        dataset_version_id=job.dataset_version_id,
        algorithm=job.algorithm,
        selected_variables=list(job.selected_variables_json or []),
        background_edges=[BackgroundEdge(**edge) for edge in job.background_edges_json or []],
        status=job.status,
        error_message=job.error_message,
        created_at=iso(job.created_at) or "",
        finished_at=iso(job.finished_at),
    )
