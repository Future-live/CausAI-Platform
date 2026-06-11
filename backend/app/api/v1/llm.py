from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.llm import (
    AnalyzeResultRequest,
    AnalyzeResultResponse,
    BackdoorAdjustmentRequest,
    BackdoorAdjustmentResponse,
    OrientEdgesRequest,
    OrientedGraphResponse,
)
from app.services.llm import get_llm_service

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/orient-edges", response_model=OrientedGraphResponse)
def orient_edges(
    payload: OrientEdgesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    return get_llm_service(settings).orient_edges(db, user, payload.job_id)


@router.post("/backdoor-adjustment", response_model=BackdoorAdjustmentResponse)
def backdoor_adjustment(
    payload: BackdoorAdjustmentRequest,
    settings: Settings = Depends(get_settings),
    _user: User = Depends(get_current_user),
):
    return get_llm_service(settings).backdoor_adjustment(payload)


@router.post("/analyze-result", response_model=AnalyzeResultResponse)
def analyze_result(
    payload: AnalyzeResultRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    return get_llm_service(settings).analyze_result(db, user, payload)
