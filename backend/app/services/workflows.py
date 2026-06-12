from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import Settings
from app.models.user import User
from app.models.workflow import AnalysisWorkflow
from app.schemas.dataset import ColumnVisibilityRequest, FilterRequest, PrepareRequest
from app.schemas.workflow import WorkflowCreate, WorkflowRead, WorkflowRunRequest, WorkflowRunResult, WorkflowStep
from app.services.datasets import create_filtered_version, create_prepared_version, update_column_visibility
from app.services.serialization import iso


def _workflow_read(workflow: AnalysisWorkflow) -> WorkflowRead:
    return WorkflowRead(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        steps=[WorkflowStep(**step) for step in workflow.steps_json or []],
        created_at=iso(workflow.created_at) or "",
        updated_at=iso(workflow.updated_at) or "",
    )


def _workflow_for_user(db: Session, user: User, workflow_id: str) -> AnalysisWorkflow:
    workflow = db.get(AnalysisWorkflow, workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


def create_workflow(db: Session, user: User, payload: WorkflowCreate) -> WorkflowRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流名称不能为空")
    workflow = AnalysisWorkflow(
        owner_id=user.id,
        name=name,
        description=payload.description.strip() if payload.description else None,
        steps_json=[step.model_dump() for step in payload.steps],
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return _workflow_read(workflow)


def list_workflows(db: Session, user: User) -> list[WorkflowRead]:
    workflows = db.scalars(
        select(AnalysisWorkflow)
        .where(AnalysisWorkflow.owner_id == user.id)
        .order_by(AnalysisWorkflow.created_at.desc())
    ).all()
    return [_workflow_read(workflow) for workflow in workflows]


def get_workflow(db: Session, user: User, workflow_id: str) -> WorkflowRead:
    return _workflow_read(_workflow_for_user(db, user, workflow_id))


def delete_workflow(db: Session, user: User, workflow_id: str) -> None:
    workflow = _workflow_for_user(db, user, workflow_id)
    db.delete(workflow)
    db.commit()


def run_workflow(
    db: Session,
    settings: Settings,
    user: User,
    workflow_id: str,
    payload: WorkflowRunRequest,
) -> WorkflowRunResult:
    workflow = _workflow_for_user(db, user, workflow_id)
    current_version_id = payload.dataset_version_id
    applied: list[WorkflowStep] = []
    skipped: list[WorkflowStep] = []
    final_version = None

    for raw_step in workflow.steps_json or []:
        step = WorkflowStep(**raw_step)
        if step.type == "prepare":
            final_version = create_prepared_version(
                db,
                settings,
                user,
                current_version_id,
                PrepareRequest(**step.payload),
            )
            current_version_id = final_version.id
            applied.append(step)
        elif step.type == "filter":
            final_version = create_filtered_version(
                db,
                settings,
                user,
                current_version_id,
                FilterRequest(**step.payload),
            )
            current_version_id = final_version.id
            applied.append(step)
        elif step.type == "columns":
            final_version = update_column_visibility(
                db,
                user,
                current_version_id,
                ColumnVisibilityRequest(**step.payload),
            )
            applied.append(step)
        else:
            skipped.append(step)

    if final_version is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流没有可执行的数据准备步骤")

    return WorkflowRunResult(
        workflow_id=workflow.id,
        initial_version_id=payload.dataset_version_id,
        final_version=final_version,
        applied_steps=applied,
        skipped_steps=skipped,
    )
