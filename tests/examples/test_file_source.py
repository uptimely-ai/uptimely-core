"""Generic JSON and CSV profile sources."""

import pathlib

import polars as pl
import pytest
from example.src import io


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


@pytest.mark.parametrize("from_parent", [False, True])
def test_read_file_resolves_relative_paths_from_example_project(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, from_parent: bool
) -> None:
    project = tmp_path / "example"
    (project / "config").mkdir(parents=True)
    (project / "config/config.json").write_text("{}", encoding="utf-8")
    (project / "data/input").mkdir(parents=True)
    (project / "data/input/records.json").write_text('[{"id": "one"}]', encoding="utf-8")
    monkeypatch.chdir(tmp_path if from_parent else project)

    assert io.read_file("data/input/records.json").collect().to_dicts() == [{"id": "one"}]


def test_read_file_rejects_missing_columns_and_invalid_types(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "records.json"
    path.write_text('[{"id": "one", "value": "invalid"}]', encoding="utf-8")

    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        io.read_file(str(path), columns=["missing"]).collect()
    with pytest.raises(ValueError, match="Unsupported column type for value: unknown"):
        io.read_file(str(path), schema={"value": "unknown"})
    with pytest.raises(pl.exceptions.InvalidOperationError):
        io.read_file(str(path), schema={"value": "float"}).collect()
