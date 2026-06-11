import pandas as pd

from app.services.dataframe import profile_columns, records


def test_profile_columns_detects_measure_and_dimension() -> None:
    df = pd.DataFrame(
        {
            "score": [1.0, 2.5, None],
            "group": ["A", "B", "A"],
        }
    )

    profiles = {column["name"]: column for column in profile_columns(df)}

    assert profiles["score"]["analysis_type"] == "measure"
    assert profiles["score"]["missing_count"] == 1
    assert profiles["group"]["analysis_type"] == "dimension"


def test_records_converts_nan_to_none() -> None:
    df = pd.DataFrame({"value": [1.0, float("nan")]})

    assert records(df) == [{"value": 1.0}, {"value": None}]
