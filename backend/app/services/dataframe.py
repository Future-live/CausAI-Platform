from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_csv(path: str | Path, usecols: list[str] | None = None) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)


def json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{key: json_safe(value) for key, value in row.items()} for row in df.to_dict(orient="records")]


def semantic_type(series: pd.Series) -> str:
    non_empty = series.dropna()
    if non_empty.empty:
        return "empty"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    parsed = pd.to_datetime(non_empty.head(100), errors="coerce")
    if parsed.notna().mean() > 0.9:
        return "datetime"
    unique_ratio = non_empty.nunique() / max(len(non_empty), 1)
    if unique_ratio < 0.05 or non_empty.nunique() < 20:
        return "categorical"
    return "text"


def profile_columns(df: pd.DataFrame, enabled_columns: set[str] | None = None) -> list[dict[str, Any]]:
    enabled_columns = enabled_columns or set(df.columns)
    profiles: list[dict[str, Any]] = []
    for column in df.columns:
        series = df[column]
        is_numeric = pd.api.types.is_numeric_dtype(series)
        profiles.append(
            {
                "name": column,
                "dtype": str(series.dtype),
                "analysis_type": "measure" if is_numeric else "dimension",
                "semantic_type": semantic_type(series),
                "enabled": column in enabled_columns,
                "missing_count": int(series.isna().sum()),
                "unique_count": int(series.nunique(dropna=True)),
            }
        )
    return profiles
