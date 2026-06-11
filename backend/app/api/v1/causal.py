from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.causal import CausalJobCreate, CausalJobRead, CausalJobResult, EffectRequest, EffectResponse
from app.services.causal import calculate_effect, create_job, get_job, get_job_result, list_jobs

router = APIRouter(prefix="/causal", tags=["causal"])


@router.post("/jobs", response_model=CausalJobRead)
def submit_job(
    payload: CausalJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    return create_job(db, settings, user, payload, background_tasks)


@router.get("/jobs", response_model=list[CausalJobRead])
def jobs(
    dataset_version_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_jobs(db, user, dataset_version_id)


@router.get("/jobs/{job_id}", response_model=CausalJobRead)
def job_detail(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_job(db, user, job_id)


@router.get("/jobs/{job_id}/result", response_model=CausalJobResult)
def job_result(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_job_result(db, user, job_id)


@router.post("/effect", response_model=EffectResponse)
def effect(payload: EffectRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return calculate_effect(db, user, payload)
