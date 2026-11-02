"""Tests for static Explorer directory and ZIP exports."""

import json
import pathlib
import zipfile

import pytest
from support import examples as example_support

from uptimely import project
from uptimely.explorer import export, presentation


def _write_snapshot(
    project_root: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
) -> pathlib.Path:
    bundle = example_bundle_factory()
    data = presentation.build_presentation_data(bundle.spec_definition, bundle.execution_plan)
    snapshot_path = project_root / project.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(presentation.serialize_presentation_data(data), encoding="utf-8")
    return snapshot_path


def test_export_directory_uses_relative_assets_and_preserves_snapshot_bytes(
    tmp_path: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    snapshot_path = _write_snapshot(project_root, example_bundle_factory)
    snapshot_bytes = snapshot_path.read_bytes()
    output = tmp_path / "docs" / "examples" / "pump"

    exported = export.export_static(project_root, output)

    assert exported == output.resolve()
    assert (output / "index.html").is_file()
    assert (output / "css" / "explorer.css").is_file()
    assert (output / "js" / "app.js").is_file()
    assert (output / "data" / "explorer.json").read_bytes() == snapshot_bytes
    config = (output / "config.js").read_text(encoding="utf-8")
    assert '"./data/explorer.json"' in config
    assert "/api/explorer" not in config
    index = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="./css/explorer.css"' in index
    assert 'src="./js/app.js"' in index


def test_export_zip_contains_static_frontend_and_data(
    tmp_path: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    snapshot_path = _write_snapshot(project_root, example_bundle_factory)
    output = tmp_path / "artifacts" / "pump.zip"

    exported = export.export_static(project_root, output)

    assert exported == output.resolve()
    with zipfile.ZipFile(output) as archive:
        assert {
            "index.html",
            "config.js",
            "css/explorer.css",
            "js/app.js",
            "data/explorer.json",
        } <= set(archive.namelist())
        assert archive.read("data/explorer.json") == snapshot_path.read_bytes()
        config = archive.read("config.js").decode("utf-8")
        assert '"./data/explorer.json"' in config
        assert "/api/explorer" not in config


def test_export_reads_snapshot_once(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    snapshot_path = _write_snapshot(project_root, example_bundle_factory)
    original_read_bytes = pathlib.Path.read_bytes
    snapshot_reads = 0

    def track_snapshot_read(path: pathlib.Path) -> bytes:
        nonlocal snapshot_reads
        if path == snapshot_path:
            snapshot_reads += 1
        return original_read_bytes(path)

    monkeypatch.setattr(pathlib.Path, "read_bytes", track_snapshot_read)

    export.export_static(project_root, tmp_path / "export.zip")

    assert snapshot_reads == 1


@pytest.mark.parametrize("kind", ["missing", "invalid"])
def test_export_rejects_missing_or_invalid_snapshot(
    tmp_path: pathlib.Path,
    kind: str,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    if kind == "invalid":
        snapshot_path = project_root / project.EXPLORER_DATA_FILE
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_text(json.dumps({"format_version": 1}), encoding="utf-8")

    with pytest.raises((FileNotFoundError, ValueError), match="Explorer snapshot"):
        export.export_static(project_root, tmp_path / "missing.zip")
