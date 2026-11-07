"""Tests for static Explorer directory and ZIP exports."""

import dataclasses
import json
import pathlib
import zipfile

import polars as pl
import pytest
from support import examples as example_support

from uptimely import engine, project
from uptimely.explorer import export, presentation
from uptimely.run import models, store


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
    assert (output / "js" / "application" / "bootstrap.js").is_file()
    assert (output / "js" / "application" / "view_controller.js").is_file()
    assert (output / "js" / "catalogs" / "catalog_renderer.js").is_file()
    assert (output / "js" / "lineage" / "feature_lineage.js").is_file()
    assert (output / "css" / "lineage.css").is_file()
    assert (output / "js" / "animation" / "playback_controller.js").is_file()
    assert (output / "data" / "explorer.json").read_bytes() == snapshot_bytes
    config = (output / "config.js").read_text(encoding="utf-8")
    assert '"./data/explorer.json"' in config
    assert "/api/explorer" not in config
    assert '"./data/run.json"' in config
    assert json.loads((output / "data/run.json").read_bytes()) == {
        "run": None,
        "logs": [],
        "previews": {},
    }
    index = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="./css/explorer.css"' in index
    assert 'src="./js/application/bootstrap.js"' in index


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
            "js/application/bootstrap.js",
            "js/application/view_controller.js",
            "js/catalogs/catalog_renderer.js",
            "js/lineage/feature_lineage.js",
            "css/lineage.css",
            "js/animation/playback_controller.js",
            "js/rendering/shared_markup.js",
            "js/navigation/sidebar_controls.js",
            "js/theme/tailwind_theme.js",
            "data/explorer.json",
            "data/run.json",
        } <= set(archive.namelist())
        assert archive.read("data/explorer.json") == snapshot_path.read_bytes()
        config = archive.read("config.js").decode("utf-8")
        assert '"./data/explorer.json"' in config
        assert "/api/explorer" not in config
        assert '"./data/run.json"' in config
        assert json.loads(archive.read("data/run.json"))["run"] is None


@pytest.mark.parametrize("suffix", ["", ".zip"])
def test_export_includes_validated_run_previews_and_all_log_pages(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_bundle_factory: example_support.BundleFactory,
    suffix: str,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_snapshot(project_root, example_bundle_factory)
    bundle = dataclasses.replace(example_bundle_factory(), project_root=project_root)
    runtime = engine.Engine(bundle, engine.EngineConfig())
    frame = pl.DataFrame({"value": range(20)})
    result = engine.ExecutionResult(
        datasets={"telemetry": frame},
        calculated_outputs={},
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=6,
    )
    monkeypatch.setattr(runtime, "_execute", lambda **kwargs: result)
    runtime.run(preview_rows=10)
    runs = store.RunStore(project_root)
    manifest = runs.read_manifest()
    entries = [
        models.LogEntry(
            timestamp=manifest.started_at,
            level="DEBUG",
            logger="demo",
            message=f"Event {index}",
        )
        for index in range(1001)
    ]
    (runs.root / manifest.log_path).write_text(
        "".join(entry.model_dump_json() + "\n" for entry in entries), encoding="utf-8"
    )
    output = tmp_path / f"export{suffix}"

    export.export_static(project_root, output)

    if suffix:
        with zipfile.ZipFile(output) as archive:
            snapshot = json.loads(archive.read("data/run.json"))
    else:
        snapshot = json.loads((output / "data/run.json").read_bytes())
    assert snapshot["run"] == manifest.model_dump(mode="json")
    assert snapshot["logs"] == [entry.model_dump(mode="json") for entry in entries]
    assert snapshot["previews"]["telemetry"]["rows"] == [[value] for value in range(10)]
    assert snapshot["previews"]["telemetry"]["columns"] == [{"name": "value", "dtype": "Int64"}]

    (runs.root / manifest.profiles["telemetry"].preview_path).unlink()
    with pytest.raises(FileNotFoundError):
        export.export_static(project_root, tmp_path / "incomplete")


def test_export_rejects_invalid_run_manifest(
    tmp_path: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    _write_snapshot(tmp_path, example_bundle_factory)
    runs = store.RunStore(tmp_path)
    runs.root.mkdir()
    (runs.root / models.MANIFEST_FILE).write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        export.export_static(tmp_path, tmp_path / "invalid")


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
