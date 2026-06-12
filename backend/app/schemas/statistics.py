from typing import Any, Literal

from pydantic import BaseModel, Field


class ChartSuggestion(BaseModel):
    chart_type: Literal["scatter", "bar", "line", "boxplot", "pixel"]
    title: str
    reason: str
    x: str | None = None
    y: str | None = None
    color: str | None = None


class CorrelationResponse(BaseModel):
    method: str
    columns: list[str]
    matrix: list[list[float | None]]


class GroupByMetric(BaseModel):
    column: str
    agg: Literal["count", "mean", "median", "sum", "min", "max"]
    alias: str | None = None


class GroupByRequest(BaseModel):
    group_by: list[str] = Field(min_length=1)
    metrics: list[GroupByMetric] = Field(default_factory=list)
    limit: int = Field(default=500, ge=1, le=5000)


class GroupByResponse(BaseModel):
    rows: list[dict[str, Any]]


class StatisticalTestRequest(BaseModel):
    test_type: Literal["t_test", "anova", "chi_square"]
    group_column: str | None = None
    value_column: str | None = None
    x: str | None = None
    y: str | None = None
    groups: list[str] | None = None


class StatisticalTestResponse(BaseModel):
    test_type: str
    statistic: float
    p_value: float
    degrees_of_freedom: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OutlierItem(BaseModel):
    column: str
    count: int
    ratio: float
    lower_bound: float
    upper_bound: float


class OutlierResponse(BaseModel):
    method: str
    items: list[OutlierItem]
