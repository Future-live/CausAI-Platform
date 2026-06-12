from __future__ import annotations

import math
from typing import Iterable

import pandas as pd
from fastapi import HTTPException, status
from scipy import stats
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.dataset import DatasetVersion
from app.models.user import User
from app.schemas.statistics import (
    ChartSuggestion,
    CorrelationResponse,
    GroupByRequest,
    GroupByResponse,
    OutlierItem,
    OutlierResponse,
    StatisticalTestRequest,
    StatisticalTestResponse,
)
from app.services.dataframe import read_dataframe, records


def _version_for_user(db: Session, version_id: str, user: User) -> DatasetVersion:
    version = db.scalar(
        select(DatasetVersion)
        .options(selectinload(DatasetVersion.dataset))
        .where(DatasetVersion.id == version_id)
    )
    if not version or version.dataset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据版本不存在")
    return version


def _df_for_user(db: Session, version_id: str, user: User) -> pd.DataFrame:
    version = _version_for_user(db, version_id, user)
    return read_dataframe(version.storage_path)


def _ensure_columns(df: pd.DataFrame, columns: Iterable[str | None]) -> None:
    missing = [column for column in columns if column and column not in df.columns]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"字段不存在: {', '.join(missing)}")


def chart_suggestions(db: Session, user: User, version_id: str) -> list[ChartSuggestion]:
    df = _df_for_user(db, version_id, user)
    profiles = []
    for column in df.columns:
        series = df[column]
        profiles.append(
            {
                "name": column,
                "numeric": pd.api.types.is_numeric_dtype(series),
                "datetime": pd.api.types.is_datetime64_any_dtype(series),
                "unique": int(series.nunique(dropna=True)),
            }
        )
    numeric = [item["name"] for item in profiles if item["numeric"]]
    categorical = [item["name"] for item in profiles if not item["numeric"] and item["unique"] <= 30]
    suggestions: list[ChartSuggestion] = []
    if len(numeric) >= 2:
        suggestions.append(
            ChartSuggestion(
                chart_type="scatter",
                title=f"{numeric[0]} 与 {numeric[1]} 的关系",
                reason="两个数值字段适合用散点图观察相关性、聚集和异常点。",
                x=numeric[0],
                y=numeric[1],
                color=categorical[0] if categorical else None,
            )
        )
        suggestions.append(
            ChartSuggestion(
                chart_type="pixel",
                title="数值字段密度视图",
                reason="多个数值字段可以用像素图快速查看局部密度和分布形态。",
                x=numeric[0],
                y=numeric[1],
            )
        )
    if categorical and numeric:
        suggestions.append(
            ChartSuggestion(
                chart_type="boxplot",
                title=f"{categorical[0]} 分组下的 {numeric[0]} 分布",
                reason="类别字段与数值字段适合用箱线图比较分组差异。",
                x=categorical[0],
                y=numeric[0],
            )
        )
        suggestions.append(
            ChartSuggestion(
                chart_type="bar",
                title=f"{categorical[0]} 的分组统计",
                reason="类别字段适合用条形图展示数量或聚合指标。",
                x=categorical[0],
                y=numeric[0],
            )
        )
    if len(numeric) >= 2:
        suggestions.append(
            ChartSuggestion(
                chart_type="line",
                title=f"{numeric[1]} 随 {numeric[0]} 的趋势",
                reason="两个数值字段可用折线图观察连续变化关系。",
                x=numeric[0],
                y=numeric[1],
            )
        )
    return suggestions[:8]


def correlation_matrix(
    db: Session,
    user: User,
    version_id: str,
    method: str = "pearson",
) -> CorrelationResponse:
    df = _df_for_user(db, version_id, user)
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可计算相关性的数值字段")
    corr = numeric_df.corr(method=method)
    matrix = [
        [None if pd.isna(value) else float(value) for value in row]
        for row in corr.to_numpy().tolist()
    ]
    return CorrelationResponse(method=method, columns=list(corr.columns), matrix=matrix)


def groupby_stats(db: Session, user: User, version_id: str, payload: GroupByRequest) -> GroupByResponse:
    df = _df_for_user(db, version_id, user)
    metric_columns = [metric.column for metric in payload.metrics]
    _ensure_columns(df, [*payload.group_by, *metric_columns])
    grouped = df.groupby(payload.group_by, dropna=False)
    if not payload.metrics:
        result = grouped.size().reset_index(name="row_count")
    else:
        frames = []
        for metric in payload.metrics:
            alias = metric.alias or f"{metric.column}_{metric.agg}"
            if metric.agg == "count":
                series = grouped[metric.column].count().rename(alias)
            else:
                if not pd.api.types.is_numeric_dtype(df[metric.column]):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{metric.column} 不是数值字段，不能执行 {metric.agg}",
                    )
                series = getattr(grouped[metric.column], metric.agg)().rename(alias)
            frames.append(series)
        result = pd.concat(frames, axis=1).reset_index()
    return GroupByResponse(rows=records(result.head(payload.limit)))


def statistical_test(
    db: Session,
    user: User,
    version_id: str,
    payload: StatisticalTestRequest,
) -> StatisticalTestResponse:
    df = _df_for_user(db, version_id, user)
    if payload.test_type in {"t_test", "anova"}:
        _ensure_columns(df, [payload.group_column, payload.value_column])
        if not payload.group_column or not payload.value_column:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要 group_column 和 value_column")
        groups = payload.groups or [str(item) for item in df[payload.group_column].dropna().unique().tolist()]
        samples = [
            pd.to_numeric(
                df.loc[df[payload.group_column].astype(str) == str(group), payload.value_column],
                errors="coerce",
            ).dropna()
            for group in groups
        ]
        samples = [sample for sample in samples if not sample.empty]
        if payload.test_type == "t_test":
            if len(samples) != 2:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="t_test 需要两个有效分组")
            result = stats.ttest_ind(samples[0], samples[1], equal_var=False)
            return StatisticalTestResponse(
                test_type="t_test",
                statistic=float(result.statistic),
                p_value=float(result.pvalue),
                details={"groups": groups[:2]},
            )
        if len(samples) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="anova 至少需要两个有效分组")
        result = stats.f_oneway(*samples)
        return StatisticalTestResponse(
            test_type="anova",
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            details={"groups": groups},
        )

    _ensure_columns(df, [payload.x, payload.y])
    if not payload.x or not payload.y:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chi_square 需要 x 和 y")
    table = pd.crosstab(df[payload.x], df[payload.y])
    statistic, p_value, dof, _expected = stats.chi2_contingency(table)
    return StatisticalTestResponse(
        test_type="chi_square",
        statistic=float(statistic),
        p_value=float(p_value),
        degrees_of_freedom=float(dof),
        details={"x": payload.x, "y": payload.y, "shape": list(table.shape)},
    )


def outliers(
    db: Session,
    user: User,
    version_id: str,
    columns: list[str] | None = None,
) -> OutlierResponse:
    df = _df_for_user(db, version_id, user)
    target_columns = columns or list(df.select_dtypes(include="number").columns)
    _ensure_columns(df, target_columns)
    items: list[OutlierItem] = []
    for column in target_columns:
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if math.isclose(float(iqr), 0.0):
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        count = int(((series < lower) | (series > upper)).sum())
        items.append(
            OutlierItem(
                column=column,
                count=count,
                ratio=float(count / len(series)),
                lower_bound=float(lower),
                upper_bound=float(upper),
            )
        )
    return OutlierResponse(method="iqr", items=items)
