import pytest
from pydantic import ValidationError

from app.schemas.causal import BackgroundEdge
from app.schemas.dataset import QuantileFilter


def test_background_edge_rejects_self_edge() -> None:
    with pytest.raises(ValidationError):
        BackgroundEdge(source="x", target="x")


def test_quantile_filter_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        QuantileFilter(column="x", low=0.8, high=0.2)
