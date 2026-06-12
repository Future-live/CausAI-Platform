from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.dataset import DatasetVersionRead


class WorkflowStep(BaseModel):
    type: Literal["prepare", "filter", "columns", "chart", "causal"]
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)


class WorkflowRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    steps: list[WorkflowStep]
    created_at: str
    updated_at: str


class WorkflowRunRequest(BaseModel):
    dataset_version_id: str


class WorkflowRunResult(BaseModel):
    workflow_id: str
    initial_version_id: str
    final_version: DatasetVersionRead
    applied_steps: list[WorkflowStep]
    skipped_steps: list[WorkflowStep] = Field(default_factory=list)
