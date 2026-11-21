"""Tests for the fixed analytics project layout."""

import json
import pathlib
import shlex

import pydantic
import pytest

from uptimely import application
from uptimely import plan as plan_module


def test_default_spec_attribute() -> None:
    assert application.DEFAULT_SPEC_ATTRIBUTE == "python_spec"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (application.CONFIG_DIR, "config"),
        (application.SPEC_SOURCE_DIR, "spec"),
        (application.SPEC_PYTHON_ENTRY_FILE, "spec/spec.py"),
        (application.SPEC_JSON_ENTRY_FILE, "spec/spec.json"),
        (application.COMPILER_CONFIG_FILE, "config/compiler.json"),
        (application.CONFIG_FILE, "uptimely.toml"),
        (application.DATA_DIR, "data"),
        (application.FUNCTIONS_DIR, "functions"),
        (application.ARTIFACTS_DIR, "artifacts"),
        (application.EXPLORER_DATA_FILE, "artifacts/explorer.json"),
        (application.BUILD_OUTPUT_DIR, "artifacts/build"),
        (application.BUILD_MANIFEST_FILE, "artifacts/build/build.json"),
        (application.BUILD_SPEC_FILE, "artifacts/build/spec.json"),
        (application.BUILD_EXECUTION_PLAN_FILE, "artifacts/build/execution_plan.json"),
    ],
)
def test_standard_paths(path: pathlib.Path, expected: str) -> None:
    assert path == pathlib.Path(expected)
    assert not path.is_absolute()
    assert pathlib.Path("example") / path == pathlib.Path("example") / expected


def _manifest_data() -> dict[str, object]:
    return {
        "build_version": application.BUILD_VERSION,
        "uptimely_version": "0.2.0.dev0",
        "features": None,
        "artifacts": {
            "spec": "spec.json",
            "execution_plan": "execution_plan.json",
            "code": {"language": "python", "requirements": None, "src": None},
        },
    }


def _write_bundle(project_root: pathlib.Path) -> pathlib.Path:
    build_root = project_root / application.BUILD_OUTPUT_DIR
    build_root.mkdir(parents=True)
    (build_root / "spec.json").write_text("{}", encoding="utf-8")
    (build_root / "execution_plan.json").write_text(
        json.dumps(
            {
                "plan_version": plan_module.PLAN_VERSION,
                "required_backend": "polars",
                "invocations": [],
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (build_root / "build.json").write_text(json.dumps(_manifest_data()), encoding="utf-8")
    return build_root


def test_build_manifest_normalizes_feature_selection() -> None:
    data = _manifest_data()
    data["features"] = ["pressure", "temperature", "pressure"]

    manifest = application.BuildManifest.model_validate(data)

    assert manifest.features == ["pressure", "temperature"]


def test_build_manifest_accepts_code_artifacts() -> None:
    data = _manifest_data()
    data["artifacts"] = {
        "spec": "spec.json",
        "execution_plan": "execution_plan.json",
        "code": {
            "language": "python",
            "requirements": "runtime/pyproject.toml",
            "src": "packages/project",
        },
    }

    manifest = application.BuildManifest.model_validate(data)

    assert manifest.artifacts.code.model_dump() == {
        "language": "python",
        "requirements": "runtime/pyproject.toml",
        "src": "packages/project",
    }


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("src", "../outside"),
        ("src", "packages/project/nested"),
        ("requirements", "../outside.toml"),
        ("requirements", "packages/project/requirements.toml"),
    ],
)
def test_build_manifest_validates_code_paths(field: str, path: str) -> None:
    data = _manifest_data()
    data["artifacts"] = {
        "spec": "spec.json",
        "execution_plan": "execution_plan.json",
        "code": {"language": "python", "requirements": None, "src": None, field: path},
    }

    with pytest.raises(pydantic.ValidationError):
        application.BuildManifest.model_validate(data)


def test_build_manifest_defaults_spec_source_for_older_bundles() -> None:
    manifest = application.BuildManifest.model_validate(_manifest_data())

    assert manifest.spec_source is None


@pytest.mark.parametrize("version", [0, 2, 3, 4, 5, 6, 8, "7", True])
def test_build_manifest_rejects_unsupported_or_noninteger_version(version: object) -> None:
    data = _manifest_data()
    data["build_version"] = version

    with pytest.raises(pydantic.ValidationError, match="build_version"):
        application.BuildManifest.model_validate(data)


def test_build_manifest_requires_nonempty_explicit_feature_selection() -> None:
    data = _manifest_data()
    data["features"] = []

    with pytest.raises(pydantic.ValidationError, match="nonempty list"):
        application.BuildManifest.model_validate(data)


def test_load_build_bundle_validates_and_loads_all_declared_artifacts(
    tmp_path: pathlib.Path,
) -> None:
    _write_bundle(tmp_path)

    bundle = application.load_build_bundle(tmp_path)

    assert bundle.project_root == tmp_path.resolve()
    assert bundle.root == tmp_path.resolve() / application.BUILD_OUTPUT_DIR
    assert bundle.manifest.features is None
    assert bundle.spec_path == bundle.root / "spec.json"
    assert bundle.spec_definition.spec_version == 9
    assert bundle.execution_plan_path == bundle.root / "execution_plan.json"
    assert bundle.execution_plan.invocations == []


@pytest.mark.parametrize("validate", [True, False])
def test_bundle_spec_semantic_validation_is_optional(
    tmp_path: pathlib.Path, validate: bool
) -> None:
    root = _write_bundle(tmp_path)
    (root / "spec.json").write_text(
        '{"dimensions": {"child": {"resolutions": {"child": '
        '{"key": "child", "type": "integer", "parent": "missing"}}}}}',
        encoding="utf-8",
    )

    if validate:
        with pytest.raises(application.BuildError, match="unknown parent resolution"):
            application.load_build_bundle(tmp_path)
        with (
            pytest.raises(application.BuildError, match="unknown parent resolution"),
            application.read_build_bundle(tmp_path),
        ):
            pytest.fail("Invalid Spec must not be yielded")
    else:
        assert application.load_build_bundle(tmp_path, validate=False).spec_definition
        with application.read_build_bundle(tmp_path, validate=False) as bundle:
            assert (
                bundle.spec_definition.dimensions["child"].resolutions["child"].parent == "missing"
            )


@pytest.mark.parametrize("artifact", ["spec.json", "execution_plan.json", "build.json"])
def test_bundle_validation_opt_out_preserves_structure_checks(
    tmp_path: pathlib.Path, artifact: str
) -> None:
    root = _write_bundle(tmp_path)
    (root / artifact).write_text('{"invalid": true}', encoding="utf-8")

    with pytest.raises(application.BuildError):
        application.load_build_bundle(tmp_path, validate=False)


def test_load_build_bundle_reports_missing_build_with_quoted_recovery_command(
    tmp_path: pathlib.Path,
) -> None:
    project_root = tmp_path / "project with spaces;echo invalid"

    with pytest.raises(application.BuildError, match="No active build found") as error:
        application.load_build_bundle(project_root)

    assert error.value.status == "missing"
    assert shlex.quote(str(project_root.resolve())) in error.value.recovery_command


def test_load_build_bundle_rejects_malformed_manifest(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "build.json").write_text('{"build_version":', encoding="utf-8")

    with pytest.raises(application.BuildError, match="invalid.*manifest"):
        application.load_build_bundle(tmp_path)


def test_load_build_bundle_rejects_unsupported_schema(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    manifest = _manifest_data()
    manifest["build_version"] = application.BUILD_VERSION + 1
    (build_root / "build.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(application.BuildError, match="Unsupported build version"):
        application.load_build_bundle(tmp_path)


def test_load_build_bundle_reports_missing_required_artifact(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "spec.json").unlink()

    with pytest.raises(application.BuildError, match="incomplete.*missing artifact spec.json"):
        application.load_build_bundle(tmp_path)


def test_build_manifest_rejects_paths_that_escape_the_bundle() -> None:
    manifest = _manifest_data()
    manifest["artifacts"] = {
        "spec": "../spec.json",
        "execution_plan": "execution_plan.json",
        "code": {"language": "python", "requirements": None, "src": None},
    }

    with pytest.raises(pydantic.ValidationError, match="stay within the build directory"):
        application.BuildManifest.model_validate(manifest)


def test_load_build_bundle_rejects_artifact_symlink_that_escapes_bundle(
    tmp_path: pathlib.Path,
) -> None:
    build_root = _write_bundle(tmp_path)
    spec_path = build_root / "spec.json"
    spec_path.unlink()
    external_spec = tmp_path / "external-spec.json"
    external_spec.write_text("{}", encoding="utf-8")
    spec_path.symlink_to(external_spec)

    with pytest.raises(application.BuildError, match="invalid.*escapes its bundle"):
        application.load_build_bundle(tmp_path)


def test_load_build_bundle_does_not_validate_unlisted_files(
    tmp_path: pathlib.Path,
) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "unlisted.json").write_text("{invalid", encoding="utf-8")

    loaded_bundle = application.load_build_bundle(tmp_path)

    assert set(loaded_bundle.manifest.artifacts.model_dump()) == {
        "spec",
        "execution_plan",
        "explorer",
        "code",
    }


def test_load_build_bundle_rejects_invalid_saved_plan(tmp_path: pathlib.Path) -> None:
    build_root = _write_bundle(tmp_path)
    (build_root / "execution_plan.json").write_text('{"invocations": []}', encoding="utf-8")

    with pytest.raises(application.BuildError, match="invalid.*cannot load execution plan"):
        application.load_build_bundle(tmp_path)
