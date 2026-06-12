from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SUPPORTED_DATASET_FORMATS = [
    {
        "extension": ".csv",
        "label": "CSV",
        "description": "逗号分隔文本，推荐使用 UTF-8 或 UTF-8-SIG 编码。",
    },
    {
        "extension": ".tsv",
        "label": "TSV",
        "description": "制表符分隔文本，适合从表格软件或数据库导出。",
    },
    {
        "extension": ".txt",
        "label": "Delimited TXT",
        "description": "常见分隔文本，系统会尝试自动识别分隔符。",
    },
    {
        "extension": ".json",
        "label": "JSON",
        "description": "JSON 数组或对象结构，会转换为二维表。",
    },
    {
        "extension": ".jsonl",
        "label": "JSON Lines",
        "description": "每行一个 JSON 对象，适合日志或流式导出数据。",
    },
    {
        "extension": ".xlsx",
        "label": "Excel Workbook",
        "description": "Excel 工作簿，默认读取第一个 Sheet。",
    },
    {
        "extension": ".xls",
        "label": "Legacy Excel",
        "description": "旧版 Excel 工作簿，默认读取第一个 Sheet。",
    },
]

SUPPORTED_DATASET_EXTENSIONS = {item["extension"] for item in SUPPORTED_DATASET_FORMATS}


def dataset_extension(path_or_name: str | Path) -> str:
    return Path(str(path_or_name)).suffix.lower()


def is_supported_dataset_file(path_or_name: str | Path) -> bool:
    return dataset_extension(path_or_name) in SUPPORTED_DATASET_EXTENSIONS


def read_csv(path: str | Path, usecols: list[str] | None = None) -> pd.DataFrame:
    return read_dataframe(path, usecols=usecols)


def _read_delimited(path: str | Path, sep: str | None, usecols: list[str] | None) -> pd.DataFrame:
    kwargs: dict[str, Any] = {"encoding": "utf-8-sig", "usecols": usecols}
    if sep is not None:
        kwargs["sep"] = sep
    else:
        kwargs["sep"] = None
        kwargs["engine"] = "python"
    try:
        return pd.read_csv(path, **kwargs)
    except UnicodeDecodeError:
        kwargs["encoding"] = "gb18030"
        return pd.read_csv(path, **kwargs)


def _apply_usecols(df: pd.DataFrame, usecols: list[str] | None) -> pd.DataFrame:
    if usecols is None:
        return df
    missing = [column for column in usecols if column not in df.columns]
    if missing:
        raise ValueError(f"字段不存在: {', '.join(missing)}")
    return df[usecols]


def read_dataframe(path: str | Path, usecols: list[str] | None = None) -> pd.DataFrame:
    extension = dataset_extension(path)
    if extension == ".csv":
        return _read_delimited(path, ",", usecols)
    if extension == ".tsv":
        return _read_delimited(path, "\t", usecols)
    if extension == ".txt":
        return _read_delimited(path, None, usecols)
    if extension == ".jsonl":
        return _apply_usecols(pd.read_json(path, lines=True), usecols)
    if extension == ".json":
        try:
            df = pd.read_json(path, lines=True)
        except ValueError:
            df = pd.read_json(path)
        return _apply_usecols(df, usecols)
    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(path, usecols=usecols)
    supported = ", ".join(sorted(SUPPORTED_DATASET_EXTENSIONS))
    raise ValueError(f"不支持的文件类型 {extension or '(无扩展名)'}，支持: {supported}")


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
