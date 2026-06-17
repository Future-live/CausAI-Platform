from fastapi import APIRouter, Depends
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.llm_config import UserLLMConfig
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.llm import (
    AnalyzeResultRequest,
    AnalyzeResultResponse,
    BackdoorAdjustmentRequest,
    BackdoorAdjustmentResponse,
    LLMConfigRead,
    LLMConfigSaveRequest,
    LLMProviderConfig,
    OrientEdgesRequest,
    OrientedGraphResponse,
    SemanticProfileRequest,
    SemanticProfileResponse,
)
from app.services.llm import get_llm_service

router = APIRouter(prefix="/llm", tags=["llm"])


def _mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}****{value[-4:]}"


def _config_read(item: UserLLMConfig | None) -> LLMConfigRead:
    if not item:
        return LLMConfigRead()
    return LLMConfigRead(
        saved=True,
        base_url=item.base_url,
        model=item.model,
        domain_hint=item.domain_hint,
        has_api_key=bool(item.api_key),
        masked_api_key=_mask_api_key(item.api_key),
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


def _saved_config(db: Session, user: User) -> UserLLMConfig | None:
    return db.scalar(select(UserLLMConfig).where(UserLLMConfig.owner_id == user.id))


def _resolve_config(db: Session, user: User, incoming: LLMProviderConfig | None) -> LLMProviderConfig | None:
    saved = _saved_config(db, user)
    if not saved:
        return incoming
    incoming = incoming or LLMProviderConfig()
    return LLMProviderConfig(
        base_url=incoming.base_url or saved.base_url,
        model=incoming.model or saved.model,
        api_key=incoming.api_key or saved.api_key,
    )


@router.get("/config", response_model=LLMConfigRead)
def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _config_read(_saved_config(db, user))


@router.put("/config", response_model=LLMConfigRead)
def save_config(
    payload: LLMConfigSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = _saved_config(db, user)
    if not item and not payload.api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="首次保存账号配置时需要填写 API Key")
    if item:
        item.base_url = payload.base_url
        item.model = payload.model
        item.domain_hint = payload.domain_hint
        if payload.api_key:
            item.api_key = payload.api_key
    else:
        item = UserLLMConfig(
            owner_id=user.id,
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key or "",
            domain_hint=payload.domain_hint,
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return _config_read(item)


@router.delete("/config", response_model=MessageResponse)
def delete_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _saved_config(db, user)
    if item:
        db.delete(item)
        db.commit()
    return MessageResponse(message="模型配置已删除")


@router.post("/orient-edges", response_model=OrientedGraphResponse)
def orient_edges(
    payload: OrientEdgesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    return get_llm_service(settings).orient_edges(db, user, payload.job_id, _resolve_config(db, user, payload.llm_config))


@router.post("/semantic-profile", response_model=SemanticProfileResponse)
def semantic_profile(
    payload: SemanticProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    return get_llm_service(settings).semantic_profile(
        db,
        user,
        payload.dataset_version_id,
        _resolve_config(db, user, payload.llm_config),
    )


@router.post("/backdoor-adjustment", response_model=BackdoorAdjustmentResponse)
def backdoor_adjustment(
    payload: BackdoorAdjustmentRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    payload = payload.model_copy(update={"llm_config": _resolve_config(db, user, payload.llm_config)})
    return get_llm_service(settings).backdoor_adjustment(payload)


@router.post("/analyze-result", response_model=AnalyzeResultResponse)
def analyze_result(
    payload: AnalyzeResultRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    payload = payload.model_copy(update={"llm_config": _resolve_config(db, user, payload.llm_config)})
    return get_llm_service(settings).analyze_result(db, user, payload)
