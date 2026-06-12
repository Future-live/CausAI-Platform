from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.workflow import WorkflowCreate, WorkflowRead, WorkflowRunRequest, WorkflowRunResult
from app.services.workflows import create_workflow, delete_workflow, get_workflow, list_workflows, run_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowRead])
def workflows(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list_workflows(db, user)


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create(payload: WorkflowCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_workflow(db, user, payload)


@router.get("/{workflow_id}", response_model=WorkflowRead)
def detail(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_workflow(db, user, workflow_id)


@router.delete("/{workflow_id}", response_model=MessageResponse)
def delete(workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    delete_workflow(db, user, workflow_id)
    return MessageResponse(message="已删除工作流")


@router.post("/{workflow_id}/run", response_model=WorkflowRunResult)
def run(
    workflow_id: str,
    payload: WorkflowRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    return run_workflow(db, settings, user, workflow_id, payload)
