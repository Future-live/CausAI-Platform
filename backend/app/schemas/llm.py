from pydantic import BaseModel, Field

from app.schemas.causal import BackgroundEdge


class OrientEdgesRequest(BaseModel):
    job_id: str


class OrientedGraphResponse(BaseModel):
    nodes: list[str]
    edges: list[BackgroundEdge]
    configured: bool = True


class BackdoorAdjustmentRequest(BaseModel):
    cause_var: str
    effect_var: str
    nodes: list[str] = Field(min_length=2)
    edges: list[BackgroundEdge]


class BackdoorAdjustmentResponse(BaseModel):
    adjustment_set: list[str]
    configured: bool = True


class AnalyzeResultRequest(BaseModel):
    job_id: str
    prompt: str | None = None


class AnalyzeResultResponse(BaseModel):
    analysis: str
    configured: bool = True
