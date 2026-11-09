"""Generic JSON and CSV profile sources."""

import pathlib

import polars as pl
import pytest
from examples.pump_analytics.functions import source


@pytest.mark.parametrize("extension", ["json", "csv"])
def test_read_file_supports_all_columns_selection_and_renaming(
    tmp_path: pathlib.Path, extension: str
) -> None:
    path = tmp_path / f"records.{extension}"
    frame = pl.DataFrame({"id": ["one", "two"], "value": [10.0, None], "extra": [1, 2]})
    if extension == "json":
        frame.write_json(path)
    else:
        frame.write_csv(path)

    assert source.read_file(str(path)).collect().equals(frame)
    assert (
        source.read_file(str(path), columns=["value", "id"], rename={"value": "capacity"})
        .collect()
        .equals(frame.select(pl.col("value").alias("capacity"), "id"))
    )
    assert source.read_file(str(path), columns=[]).collect().columns == []


def test_read_file_rejects_unsupported_extensions(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension: .txt"):
        source.read_file(str(tmp_path / "records.txt"))


@pytest.mark.parametrize("extension", ["json", "csv"])
def test_read_file_surfaces_missing_files(tmp_path: pathlib.Path, extension: str) -> None:
    with pytest.raises(FileNotFoundError):
        source.read_file(str(tmp_path / f"missing.{extension}")).collect()


def test_read_file_rejects_missing_columns_and_invalid_types(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "records.json"
    path.write_text('[{"id": "one", "value": "invalid"}]', encoding="utf-8")

    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        source.read_file(str(path), columns=["missing"]).collect()
    with pytest.raises(ValueError, match="Unsupported column type for value: unknown"):
        source.read_file(str(path), schema={"value": "unknown"})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        source.read_file(str(path), schema={"value": "float"}).collect()
