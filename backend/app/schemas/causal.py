from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BackgroundEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)

    @model_validator(mode="after")
    def no_self_edge(self) -> "BackgroundEdge":
        if self.source == self.target:
            raise ValueError("self edges are not allowed")
        return self


class CausalJobCreate(BaseModel):
    dataset_version_id: str
    algorithm: Literal["pc", "gies"]
    selected_variables: list[str] = Field(min_length=2)
    background_edges: list[BackgroundEdge] = Field(default_factory=list)


class CausalEdge(BaseModel):
    node1: str
    node2: str
    endpoint1: str = "TAIL"
    endpoint2: str = "ARROW"


class CausalJobRead(BaseModel):
    id: str
    dataset_version_id: str
    algorithm: str
    selected_variables: list[str]
    background_edges: list[BackgroundEdge]
    status: str
    error_message: str | None = None
    created_at: str
    finished_at: str | None = None


class CausalJobResult(BaseModel):
    job: CausalJobRead
    edges: list[CausalEdge]
    nodes: list[str]


class EffectRequest(BaseModel):
    job_id: str
    cause_var: str
    effect_var: str


class EffectResponse(BaseModel):
    kl_divergence: float
    js_divergence: float
    total_variation: float
    wasserstein_distance: float
    hellinger_distance: float
