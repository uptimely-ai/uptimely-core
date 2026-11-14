"""Generic JSON and CSV profile sources."""

import pathlib

import polars as pl
import pump_io as io
import pytest


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

    assert io.read_file(str(path)).collect().equals(frame)
    assert (
        io.read_file(str(path), columns=["value", "id"], rename={"value": "capacity"})
        .collect()
        .equals(frame.select(pl.col("value").alias("capacity"), "id"))
    )
    assert io.read_file(str(path), columns=[]).collect().columns == []


def test_read_file_rejects_unsupported_extensions(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension: .txt"):
        io.read_file(str(tmp_path / "records.txt"))


@pytest.mark.parametrize("extension", ["json", "csv"])
def test_read_file_surfaces_missing_files(tmp_path: pathlib.Path, extension: str) -> None:
    with pytest.raises(FileNotFoundError):
        io.read_file(str(tmp_path / f"missing.{extension}")).collect()


def test_read_file_rejects_missing_columns_and_invalid_types(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "records.json"
    path.write_text('[{"id": "one", "value": "invalid"}]', encoding="utf-8")

    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        io.read_file(str(path), columns=["missing"]).collect()
    with pytest.raises(ValueError, match="Unsupported column type for value: unknown"):
        io.read_file(str(path), schema={"value": "unknown"})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        io.read_file(str(path), schema={"value": "float"}).collect()


@pytest.mark.parametrize("extension", ["csv", "json"])
def test_write_file_creates_parent_and_writes_complete_profile(
    tmp_path: pathlib.Path, extension: str
) -> None:
    frame = pl.DataFrame({"pump_id": ["CWP-101"], "efficiency": [0.5]})
    output = tmp_path / "nested" / f"profile.{extension}"

    io.write_file(frame.lazy(), ["efficiency"], str(output))

    assert io.read_file(str(output)).collect().equals(frame)


def test_write_file_rejects_missing_features_and_unsupported_extensions(
    tmp_path: pathlib.Path,
) -> None:
    frame = pl.DataFrame({"pump_id": ["CWP-101"]}).lazy()
    with pytest.raises(ValueError, match="Missing profile features: efficiency"):
        io.write_file(frame, ["efficiency"], str(tmp_path / "profile.csv"))
    with pytest.raises(ValueError, match="Unsupported file extension: .txt"):
        io.write_file(frame, [], str(tmp_path / "profile.txt"))
