from pydantic import BaseModel, Field, field_validator

from app.schemas.causal import BackgroundEdge


class LLMProviderConfig(BaseModel):
    api_key: str | None = Field(default=None, max_length=4096)
    base_url: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, max_length=128)

    @field_validator("api_key", "base_url", "model", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class LLMConfigSaveRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=4096)
    domain_hint: str | None = Field(default=None, max_length=200)

    @field_validator("base_url", "model", "api_key", "domain_hint", mode="before")
    @classmethod
    def strip_values(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class LLMConfigRead(BaseModel):
    saved: bool = False
    base_url: str = ""
    model: str = ""
    domain_hint: str | None = None
    has_api_key: bool = False
    masked_api_key: str = ""
    updated_at: str | None = None


class GraphValidation(BaseModel):
    is_dag: bool
    cycles: list[list[str]] = Field(default_factory=list)
    unknown_edges: list[BackgroundEdge] = Field(default_factory=list)
    rejected_edges: list[BackgroundEdge] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EdgeOrientationEvidence(BaseModel):
    source: str
    target: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    requires_review: bool = False


class SemanticColumnProfile(BaseModel):
    name: str
    dtype: str = ""
    analysis_type: str = ""
    semantic_type: str = ""
    missing_count: int = 0
    unique_count: int = 0
    sample_values: list[str] = Field(default_factory=list)
    inferred_role: str = "unknown"
    description: str = ""
    unit: str | None = None
    evidence: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


class SemanticProfileRequest(BaseModel):
    dataset_version_id: str
    llm_config: LLMProviderConfig | None = None


class SemanticProfileResponse(BaseModel):
    configured: bool = True
    summary: str = ""
    columns: list[SemanticColumnProfile]
    warnings: list[str] = Field(default_factory=list)


class OrientEdgesRequest(BaseModel):
    job_id: str
    llm_config: LLMProviderConfig | None = None


class OrientedGraphResponse(BaseModel):
    nodes: list[str]
    edges: list[BackgroundEdge]
    configured: bool = True
    orientation_evidence: list[EdgeOrientationEvidence] = Field(default_factory=list)
    validation: GraphValidation | None = None


class BackdoorAdjustmentRequest(BaseModel):
    cause_var: str
    effect_var: str
    nodes: list[str] = Field(min_length=2)
    edges: list[BackgroundEdge]
    llm_config: LLMProviderConfig | None = None


class BackdoorAdjustmentResponse(BaseModel):
    adjustment_set: list[str]
    configured: bool = True
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    validation: GraphValidation | None = None


class AnalyzeResultRequest(BaseModel):
    job_id: str
    prompt: str | None = None
    llm_config: LLMProviderConfig | None = None
    field_profiles: list[SemanticColumnProfile] = Field(default_factory=list)


class AnalyzeResultResponse(BaseModel):
    analysis: str
    configured: bool = True
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
