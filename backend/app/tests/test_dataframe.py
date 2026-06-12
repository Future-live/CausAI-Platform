import pandas as pd

from app.services.dataframe import (
    SUPPORTED_DATASET_EXTENSIONS,
    is_supported_dataset_file,
    profile_columns,
    read_dataframe,
    records,
)


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


def test_supported_dataset_formats_cover_common_tabular_files() -> None:
    assert {".csv", ".tsv", ".txt", ".json", ".jsonl", ".xlsx", ".xls"} <= SUPPORTED_DATASET_EXTENSIONS
    assert is_supported_dataset_file("sample.tsv")
    assert not is_supported_dataset_file("sample.pdf")


def test_read_dataframe_supports_csv_tsv_and_jsonl(tmp_path) -> None:
    csv_path = tmp_path / "sample.csv"
    tsv_path = tmp_path / "sample.tsv"
    jsonl_path = tmp_path / "sample.jsonl"

    csv_path.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    tsv_path.write_text("x\ty\n1\t2\n3\t4\n", encoding="utf-8")
    jsonl_path.write_text('{"x": 1, "y": 2}\n{"x": 3, "y": 4}\n', encoding="utf-8")

    assert read_dataframe(csv_path).shape == (2, 2)
    assert read_dataframe(tsv_path)["y"].tolist() == [2, 4]
    assert read_dataframe(jsonl_path, usecols=["x"]).columns.tolist() == ["x"]


def test_read_dataframe_supports_xlsx(tmp_path) -> None:
    xlsx_path = tmp_path / "sample.xlsx"
    pd.DataFrame({"x": [1, 3], "y": [2, 4]}).to_excel(xlsx_path, index=False)

    assert read_dataframe(xlsx_path, usecols=["y"])["y"].tolist() == [2, 4]
