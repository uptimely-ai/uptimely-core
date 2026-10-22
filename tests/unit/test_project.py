"""Tests for the fixed analytics project layout."""

import json
import pathlib
import shlex

import pydantic
import pytest

from uptimely import project


def test_default_spec_attribute() -> None:
    assert project.DEFAULT_SPEC_ATTRIBUTE == "python_spec"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (project.CONFIG_DIR, "config"),
        (project.SPEC_SOURCE_DIR, "spec"),
        (project.SPEC_PYTHON_ENTRY_FILE, "spec/spec.py"),
        (project.SPEC_JSON_ENTRY_FILE, "spec/spec.json"),
        (project.COMPILER_CONFIG_FILE, "config/compiler.json"),
        (project.ENGINE_CONFIG_FILE, "config/engine.json"),
        (project.DATA_DIR, "data"),
        (project.FUNCTIONS_DIR, "functions"),
        (project.GENERATED_DIR, "_generated"),
        (project.EXPLORER_OUTPUT_DIR, "_generated/explorer"),
        (project.EXPLORER_INDEX_FILE, "_generated/explorer/index.html"),
        (project.BUILD_OUTPUT_DIR, "_generated/build"),
        (project.BUILD_MANIFEST_FILE, "_generated/build/build.json"),
        (project.BUILD_SPEC_FILE, "_generated/build/spec.json"),
        (project.BUILD_EXECUTION_PLAN_FILE, "_generated/build/execution_plan.json"),
        (project.BUILD_EXPLORER_DIR, "_generated/build/explorer"),
    ],
)
def test_standard_paths(path: pathlib.Path, expected: str) -> None:
    assert path == pathlib.Path(expected)
    assert not path.is_absolute()
    assert pathlib.Path("example") / path == pathlib.Path("example") / expected


def test_resolve_path_preserves_explicit_path(tmp_path: pathlib.Path) -> None:
    explicit_path = tmp_path / "custom.json"

    resolved_path = project.resolve_path(explicit_path, tmp_path, project.ENGINE_CONFIG_FILE)
    assert resolved_path is explicit_path


def test_resolve_path_places_default_under_project_root(tmp_path: pathlib.Path) -> None:
    assert project.resolve_path(None, tmp_path, project.ENGINE_CONFIG_FILE) == (
        tmp_path / project.ENGINE_CONFIG_FILE
    )


def test_resolve_path_uses_working_directory_when_project_root_is_missing() -> None:
    assert project.resolve_path(None, None, project.ENGINE_CONFIG_FILE) == (
        project.ENGINE_CONFIG_FILE
    )


def _manifest_data() -> dict[str, object]:
    return {
        "build_version": project.BUILD_VERSION,
        "uptimely_version": "0.2.0.dev0",
        "features": None,
        "artifacts": {
            "spec": "spec.json",
            "execution_plan": "execution_plan.json",
            "explorer": "explorer",
        },
        "explorer_files": ["assets/app.js", "index.html"],
    }


def _write_bundle(project_root: pathlib.Path) -> pathlib.Path:
    build_root = project_root / project.BUILD_OUTPUT_DIR
    explorer_root = build_root / "explorer"
    (explorer_root / "assets").mkdir(parents=True)
    (build_root / "spec.json").write_text("{}", encoding="utf-8")
    (build_root / "execution_plan.json").write_text(
        json.dumps(
            {
                "plan_version": 1,
                "required_backend": "polars",
                "resources": {},
                "callables": [],
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (explorer_root / "index.html").write_text("<html></html>", encoding="utf-8")
    (explorer_root / "assets/app.js").write_text("", encoding="utf-8")
    (build_root / "build.json").write_text(json.dumps(_manifest_data()), encoding="utf-8")
    return build_root


def test_build_manifest_normalizes_feature_selection() -> None:
    data = _manifest_data()
    data["features"] = ["pressure", "temperature", "pressure"]

    manifest = project.BuildManifest.model_validate(data)

    assert manifest.features == ["pressure", "temperature"]


def test_build_manifest_rejects_legacy_schema_version_field() -> None:
    data = _manifest_data()
    data["schema_version"] = data.pop("build_version")

    with pytest.raises(pydantic.ValidationError, match="schema_version"):
        project.BuildManifest.model_validate(data)


@pytest.mark.parametrize("version", [0, 2, "1", True])
def test_build_manifest_rejects_unsupported_or_noninteger_version(version: object) -> None:
    data = _manifest_data()
    data["build_version"] = version

    with pytest.raises(pydantic.ValidationError, match="build_version"):
        project.BuildManifest.model_validate(data)


def test_build_manifest_requires_nonempty_explicit_feature_selection() -> None:
    data = _manifest_data()
    data["features"] = []

    with pytest.raises(pydantic.ValidationError, match="nonempty list"):
        project.BuildManifest.model_validate(data)


def test_load_build_bundle_validates_and_loads_all_declared_artifacts(
    tmp_path: pathlib.Path,
) -> None:
    _write_bundle(tmp_path)

    bundle = project.load_build_bundle(tmp_path)

    assert bundle.project_root == tmp_path.resolve()
    assert bundle.root == tmp_path.resolve() / project.BUILD_OUTPUT_DIR
    assert bundle.manifest.features is None
    assert bundle.spec_path == bundle.root / "spec.json"
    assert bundle.execution_plan_path == bundle.root / "execution_plan.json"
    assert bundle.explorer_path == bundle.root / "explorer"
    assert bundle.execution_plan.callables == []


def test_load_build_bundle_reports_missing_build_with_quoted_recovery_command(
    tmp_path: pathlib.Path,
) -> None:
    project_root = tmp_path / "project with spaces;echo invalid"

    with pytest.raises(project.BuildError, match="No active build found") as error:
        project.load_build_bundle(project_root)

    assert error.value.status == "missing"
    assert shlex.quote(str(project_root.resolve())) in error.value.recovery_command


def test_load_build_bundle_rejects_malformed_manifest(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "build.json").write_text('{"build_version":', encoding="utf-8")

    with pytest.raises(project.BuildError, match="invalid.*manifest"):
        project.load_build_bundle(tmp_path)


def test_load_build_bundle_rejects_unsupported_schema(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    manifest = _manifest_data()
    manifest["build_version"] = project.BUILD_VERSION + 1
    (build_root / "build.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(project.BuildError, match="Unsupported build version"):
        project.load_build_bundle(tmp_path)


def test_load_build_bundle_reports_missing_required_artifact(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "spec.json").unlink()

    with pytest.raises(project.BuildError, match="incomplete.*missing artifact spec.json"):
        project.load_build_bundle(tmp_path)


def test_build_manifest_rejects_paths_that_escape_the_bundle() -> None:
    manifest = _manifest_data()
    manifest["artifacts"] = {
        "spec": "../spec.json",
        "execution_plan": "execution_plan.json",
        "explorer": "explorer",
    }

    with pytest.raises(pydantic.ValidationError, match="stay within the build directory"):
        project.BuildManifest.model_validate(manifest)


def test_load_build_bundle_rejects_artifact_symlink_that_escapes_bundle(
    tmp_path: pathlib.Path,
) -> None:
    build_root = _write_bundle(tmp_path)
    spec_path = build_root / "spec.json"
    spec_path.unlink()
    external_spec = tmp_path / "external-spec.json"
    external_spec.write_text("{}", encoding="utf-8")
    spec_path.symlink_to(external_spec)

    with pytest.raises(project.BuildError, match="invalid.*escapes its bundle"):
        project.load_build_bundle(tmp_path)


def test_load_build_bundle_rejects_incomplete_website_inventory(
    tmp_path: pathlib.Path,
) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "explorer/assets/app.js").unlink()

    with pytest.raises(project.BuildError, match="incomplete.*website inventory mismatch"):
        project.load_build_bundle(tmp_path)


def test_load_build_bundle_rejects_invalid_saved_plan(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "execution_plan.json").write_text('{"callables": []}', encoding="utf-8")

    with pytest.raises(project.BuildError, match="invalid.*cannot load execution plan"):
        project.load_build_bundle(tmp_path)
