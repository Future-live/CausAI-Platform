import pytest
from pydantic import ValidationError

from app.schemas.causal import BackgroundEdge, CausalJobCreate
from app.schemas.dataset import QuantileFilter
from app.schemas.favorite import FavoriteCreate
from app.schemas.workflow import WorkflowCreate


def test_background_edge_rejects_self_edge() -> None:
    with pytest.raises(ValidationError):
        BackgroundEdge(source="x", target="x")


def test_quantile_filter_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        QuantileFilter(column="x", low=0.8, high=0.2)


def test_causal_job_accepts_algorithm_params() -> None:
    job = CausalJobCreate(
        dataset_version_id="v1",
        algorithm="pc",
        selected_variables=["x", "y"],
        algorithm_params={"alpha": 0.01},
    )

    assert job.algorithm_params["alpha"] == 0.01


def test_favorite_create_accepts_group_and_snapshot() -> None:
    favorite = FavoriteCreate(
        kind="chart",
        title="chart",
        dataset_id="dataset-id",
        group_name="探索分析",
        snapshot={"columns": ["x", "y"]},
    )

    assert favorite.snapshot["columns"] == ["x", "y"]


def test_workflow_create_accepts_reproducible_steps() -> None:
    workflow = WorkflowCreate(
        name="cleaning",
        steps=[
            {"type": "prepare", "payload": {"fill_na": "median"}},
            {"type": "columns", "payload": {"enabled_columns": ["x", "y"]}},
        ],
    )

    assert [step.type for step in workflow.steps] == ["prepare", "columns"]
