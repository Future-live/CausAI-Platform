from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedRows
from app.schemas.dataset import (
    ChartDataRequest,
    ChartDataResponse,
    ColumnDistribution,
    ColumnValues,
    ColumnVisibilityRequest,
    DatasetListItem,
    DatasetRead,
    DatasetVersionRead,
    FilterRequest,
    PrepareRequest,
)
from app.services.datasets import (
    create_dataset,
    create_filtered_version,
    create_prepared_version,
    get_chart_data,
    get_column_distribution,
    get_column_values,
    get_dataset_read,
    get_rows,
    get_statistics,
    list_datasets,
    update_column_visibility,
)
from app.services.serialization import dataset_read

router = APIRouter(tags=["datasets"])


@router.post("/datasets", response_model=DatasetRead)
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> DatasetRead:
    return dataset_read(create_dataset(db, settings, user, file))


@router.get("/datasets", response_model=list[DatasetListItem])
def datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list_datasets(db, user)


@router.get("/datasets/{dataset_id}", response_model=DatasetRead)
def dataset_detail(dataset_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_dataset_read(db, user, dataset_id)


@router.get("/dataset-versions/{version_id}/rows", response_model=PaginatedRows)
def rows(
    version_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_rows(db, user, version_id, limit, offset)


@router.post("/dataset-versions/{version_id}/prepare", response_model=DatasetVersionRead)
def prepare(
    version_id: str,
    payload: PrepareRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    return create_prepared_version(db, settings, user, version_id, payload)


@router.post("/dataset-versions/{version_id}/filter", response_model=DatasetVersionRead)
def filter_dataset(
    version_id: str,
    payload: FilterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    return create_filtered_version(db, settings, user, version_id, payload)


@router.patch("/dataset-versions/{version_id}/columns", response_model=DatasetVersionRead)
def update_columns(
    version_id: str,
    payload: ColumnVisibilityRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return update_column_visibility(db, user, version_id, payload)


@router.get("/dataset-versions/{version_id}/statistics")
def statistics(version_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_statistics(db, user, version_id)


@router.get("/dataset-versions/{version_id}/columns/{column}/distribution", response_model=ColumnDistribution)
def column_distribution(
    version_id: str,
    column: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_column_distribution(db, user, version_id, column)


@router.get("/dataset-versions/{version_id}/columns/{column}/values", response_model=ColumnValues)
def column_values(
    version_id: str,
    column: str,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_column_values(db, user, version_id, column, limit)


@router.post("/dataset-versions/{version_id}/chart-data", response_model=ChartDataResponse)
def chart_data(
    version_id: str,
    payload: ChartDataRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_chart_data(db, user, version_id, payload)
