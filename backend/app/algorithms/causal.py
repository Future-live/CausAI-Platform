import csv
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from app.schemas.causal import BackgroundEdge, CausalEdge
from app.services.dataframe import read_dataframe


def _normalise_endpoint(value: object) -> str:
    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.upper()


def _validate_variables(df: pd.DataFrame, variables: list[str]) -> None:
    missing = [column for column in variables if column not in df.columns]
    if missing:
        raise ValueError(f"字段不存在: {', '.join(missing)}")
    if len(set(variables)) < 2:
        raise ValueError("至少选择两个不同变量")


def run_pc(
    data_path: str | Path,
    variables: list[str],
    background_edges: list[BackgroundEdge],
    algorithm_params: dict | None = None,
) -> list[CausalEdge]:
    from causallearn.graph.GraphNode import GraphNode
    from causallearn.search.ConstraintBased.PC import pc
    from causallearn.utils.cit import fisherz
    from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge

    df = read_dataframe(data_path, usecols=variables)
    _validate_variables(df, variables)
    numeric_df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if numeric_df.empty:
        raise ValueError("PC 算法需要至少一行完整数值数据")

    background = BackgroundKnowledge()
    for edge in background_edges:
        background.add_required_by_node(GraphNode(edge.source), GraphNode(edge.target))

    params = algorithm_params or {}
    alpha = float(params.get("alpha", 0.05))
    result = pc(
        data=numeric_df.values,
        fisherz=fisherz,
        alpha=alpha,
        background_knowledge=background,
        node_names=list(numeric_df.columns),
    )
    edges: list[CausalEdge] = []
    for edge in result.G.get_graph_edges():
        edges.append(
            CausalEdge(
                node1=str(edge.node1),
                node2=str(edge.node2),
                endpoint1=_normalise_endpoint(edge.endpoint1),
                endpoint2=_normalise_endpoint(edge.get_endpoint2()),
            )
        )
    return edges


def run_gies(
    data_path: str | Path,
    variables: list[str],
    background_edges: list[BackgroundEdge],
    algorithm_params: dict | None = None,
) -> list[CausalEdge]:
    from gies import fit_bic

    df = read_dataframe(data_path, usecols=variables)
    _validate_variables(df, variables)
    numeric_df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if numeric_df.empty:
        raise ValueError("GIES 算法需要至少一行完整数值数据")

    index = {name: i for i, name in enumerate(numeric_df.columns)}
    adjacency = np.zeros((len(index), len(index)))
    for edge in background_edges:
        if edge.source not in index or edge.target not in index:
            raise ValueError(f"背景边字段不存在: {edge.source} -> {edge.target}")
        adjacency[index[edge.source], index[edge.target]] = 1

    matrix, _score = fit_bic([numeric_df.values], [[]], A0=adjacency)
    edges: list[CausalEdge] = []
    names = list(numeric_df.columns)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if matrix[i, j] == 1:
                edges.append(CausalEdge(node1=names[i], node2=names[j]))
    return edges


def run_algorithm(
    algorithm: Literal["pc", "gies"],
    data_path: str | Path,
    variables: list[str],
    background_edges: list[BackgroundEdge],
    algorithm_params: dict | None = None,
) -> list[CausalEdge]:
    if algorithm == "pc":
        return run_pc(data_path, variables, background_edges, algorithm_params)
    if algorithm == "gies":
        return run_gies(data_path, variables, background_edges, algorithm_params)
    raise ValueError(f"不支持的算法: {algorithm}")


def write_edges_csv(path: str | Path, edges: list[CausalEdge]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Node1", "Node2", "Endpoint1", "Endpoint2"])
        writer.writeheader()
        for edge in edges:
            writer.writerow(
                {
                    "Node1": edge.node1,
                    "Node2": edge.node2,
                    "Endpoint1": edge.endpoint1,
                    "Endpoint2": edge.endpoint2,
                }
            )
