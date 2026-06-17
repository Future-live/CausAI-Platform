import pytest
from pydantic import ValidationError

from app.schemas.causal import BackgroundEdge, CausalJobCreate
from app.schemas.dataset import QuantileFilter
from app.schemas.favorite import FavoriteCreate
from app.schemas.llm import LLMConfigSaveRequest, LLMProviderConfig, SemanticColumnProfile, SemanticProfileResponse
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


def test_llm_provider_config_normalizes_empty_strings() -> None:
    config = LLMProviderConfig(api_key="  ", base_url=" https://api.example.com/v1 ", model=" demo ")

    assert config.api_key is None
    assert config.base_url == "https://api.example.com/v1"
    assert config.model == "demo"


def test_llm_config_save_request_strips_values() -> None:
    config = LLMConfigSaveRequest(
        base_url=" https://api.example.com/v1 ",
        model=" demo ",
        api_key=" sk-demo ",
        domain_hint=" education ",
    )

    assert config.base_url == "https://api.example.com/v1"
    assert config.model == "demo"
    assert config.api_key == "sk-demo"
    assert config.domain_hint == "education"


def test_semantic_profile_response_accepts_column_evidence() -> None:
    response = SemanticProfileResponse(
        configured=False,
        summary="local",
        columns=[
            SemanticColumnProfile(
                name="score",
                dtype="float64",
                analysis_type="measure",
                semantic_type="numeric",
                inferred_role="outcome",
                evidence=["字段名包含 score"],
            )
        ],
    )

    assert response.columns[0].inferred_role == "outcome"
