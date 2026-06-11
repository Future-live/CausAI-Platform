from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    analysis_type: Literal["measure", "dimension"]
    semantic_type: str
    enabled: bool = True
    missing_count: int = 0
    unique_count: int = 0


class DatasetVersionRead(BaseModel):
    id: str
    dataset_id: str
    kind: str
    row_count: int
    columns: list[ColumnProfile]
    created_at: str


class DatasetRead(BaseModel):
    id: str
    original_filename: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    latest_version: DatasetVersionRead | None = None
    created_at: str


class DatasetListItem(BaseModel):
    id: str
    original_filename: str
    row_count: int
    column_count: int
    created_at: str
    latest_version_id: str | None = None


class PrepareRequest(BaseModel):
    fill_na: Literal["none", "mean", "median", "mode"] = "none"
    drop_na: bool = False


class QuantileFilter(BaseModel):
    column: str
    low: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_range(self) -> "QuantileFilter":
        if self.low >= self.high:
            raise ValueError("low must be lower than high")
        return self


class ValueFilter(BaseModel):
    column: str
    values: list[Any]


class FilterRequest(BaseModel):
    global_low: float | None = Field(default=None, ge=0, le=1)
    global_high: float | None = Field(default=None, ge=0, le=1)
    quantile_filters: list[QuantileFilter] = Field(default_factory=list)
    value_filters: list[ValueFilter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_global_range(self) -> "FilterRequest":
        if self.global_low is None and self.global_high is None:
            return self
        if self.global_low is None or self.global_high is None or self.global_low >= self.global_high:
            raise ValueError("global_low and global_high must be provided with low < high")
        return self


class ColumnVisibilityRequest(BaseModel):
    enabled_columns: list[str]


class StatisticItem(BaseModel):
    name: str
    type: Literal["numerical", "categorical"]
    mean: float | None = None
    stdDev: float | None = None
    median: float | None = None
    missing: int = 0
    unique: int = 0


class ChartDataRequest(BaseModel):
    chart_type: Literal["scatter", "bar", "line", "boxplot", "pixel"]
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    opacity: str | None = None
    limit: int = Field(default=5000, ge=1, le=20000)


class ChartDataResponse(BaseModel):
    rows: list[dict[str, Any]]
    x_axis: str | None = None
    y_axis: str | None = None
    color: str | None = None
    size: str | None = None
    opacity: str | None = None


class ColumnDistribution(BaseModel):
    column: str
    kind: Literal["histogram", "categories"]
    labels: list[str]
    values: list[float]


class ColumnValues(BaseModel):
    column: str
    values: list[Any]
