"""Tests for root-bound project operations."""

import json
import logging
import pathlib
from unittest import mock

import pydantic
import pytest
from support import examples as example_support

import uptimely
from uptimely import application as application_module
from uptimely.application import app as application_implementation
from uptimely.build import builder, bundle
from uptimely.project import paths as project_paths
from uptimely.project import python_imports


@pytest.fixture
def app(tmp_path: pathlib.Path) -> application_module.Uptimely:
    """Create a project with a minimal discoverable source Spec."""
    spec_path = tmp_path / application_module.SPEC_JSON_ENTRY_FILE
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text('{"spec_version": 9, "name": "First build"}', encoding="utf-8")
    return application_module.Uptimely(tmp_path)


def test_uptimely_is_exported_from_package() -> None:
    assert uptimely.Uptimely is application_module.Uptimely is application_implementation.Uptimely


@pytest.mark.parametrize("root", [None, "", ".", pathlib.Path(".")])
def test_project_resolves_root_at_construction(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, root: str | pathlib.Path | None
) -> None:
    monkeypatch.chdir(tmp_path)
    app = uptimely.Uptimely() if root is None else uptimely.Uptimely(root)
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)

    assert app.root == tmp_path.resolve()
    assert not (tmp_path / application_module.ARTIFACTS_DIR).exists()


def test_project_loads_and_passes_config_to_engine(tmp_path: pathlib.Path) -> None:
    config_path = tmp_path / "uptimely.toml"
    config_path.write_text(
        '[engine.backend]\ndataframe = "POLARS"\nevaluation = "lazy"\n'
        '[paths]\nsource = "data/source.csv"\n[params]\nthreshold = 42\n',
        encoding="utf-8",
    )
    app = application_module.Uptimely(tmp_path)
    config_path.write_text("[params]\nthreshold = 99\n", encoding="utf-8")
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/spec.json").write_text(
        '{"spec_version": 9, "name": "Config test"}', encoding="utf-8"
    )

    runtime = app.create_engine(app.build())

    assert runtime.config.backend.dataframe == "POLARS"
    assert runtime.config.backend.evaluation == "lazy"
    assert runtime.parameters == {"threshold": 42}
    assert runtime.paths == {"source": "data/source.csv"}
    assert application_module.Uptimely(tmp_path).config.params.root == {"threshold": 99}


def test_project_explicit_config_and_failures(tmp_path: pathlib.Path) -> None:
    (tmp_path / "uptimely.toml").write_text("[params]\nvalue = 1\n", encoding="utf-8")
    override = tmp_path / "other.toml"
    override.write_text("[params]\nvalue = 2\n", encoding="utf-8")
    assert application_module.Uptimely(tmp_path, config_path=override).config.params.root == {
        "value": 2
    }

    with pytest.raises(FileNotFoundError):
        application_module.Uptimely(tmp_path, config_path=tmp_path / "missing.toml")
    override.write_text("[params]\nvalue = [1]\n", encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        application_module.Uptimely(tmp_path, config_path=override)


def test_project_named_config_overrides_defaults_recursively(tmp_path: pathlib.Path) -> None:
    (tmp_path / "uptimely.toml").write_text(
        '[engine]\npreview_rows = 8\n[engine.backend]\ntype = "default"\nevaluation = "eager"\n'
        '[paths]\nsource = "data/source.csv"\n[params]\nthreshold = 10\n'
        '[application]\npython_spec = "spec.spec:python_spec"\n',
        encoding="utf-8",
    )
    profile_dir = tmp_path / application_module.CONFIG_DIR
    profile_dir.mkdir()
    (profile_dir / "prod.toml").write_text(
        '[engine]\npreview_rows = 12\n[engine.backend]\ntype = "production"\n'
        "[params]\nthreshold = 42\n"
        '[application]\nsrc_path = "production-src"\n',
        encoding="utf-8",
    )

    app = application_module.Uptimely(tmp_path, config="prod")

    assert app.config_path == (profile_dir / "prod.toml").resolve()
    assert app.config.engine.backend.type == "production"
    assert app.config.engine.backend.evaluation == "eager"
    assert app.config.engine.preview_rows == 12
    assert app.config.paths.root == {"source": "data/source.csv"}
    assert app.config.params.root == {"threshold": 42}
    assert app.config.application.python_spec == "spec.spec:python_spec"
    assert app.config.application.src_path == "production-src"


def test_project_build_uses_configured_source_and_cli_overrides(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "configured.json").write_text(
        '{"spec_version": 9, "name": "Configured source"}', encoding="utf-8"
    )
    override_spec = tmp_path / "override.json"
    override_spec.write_text('{"spec_version": 9, "name": "CLI source"}', encoding="utf-8")
    (tmp_path / "configured-src").mkdir()
    (tmp_path / "uptimely.toml").write_text(
        '[application]\njson_spec = "spec/configured.json"\nsrc_path = "configured-src"\n'
        "[engine]\npreview_rows = 11\n",
        encoding="utf-8",
    )
    app = application_module.Uptimely(tmp_path)
    working_directory = tmp_path / "working-directory"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)

    configured_build = app.build()
    override_build = app.build(json_spec=override_spec, src_path=pathlib.Path("configured-src"))

    assert configured_build.spec_definition.name == "Configured source"
    assert override_build.spec_definition.name == "CLI source"
    assert app.config.engine.preview_rows == 11


def test_project_config_rejects_multiple_spec_sources_and_invalid_preview_rows(
    tmp_path: pathlib.Path,
) -> None:
    config_path = tmp_path / "uptimely.toml"
    config_path.write_text(
        '[application]\npython_spec = "spec.spec:python_spec"\njson_spec = "spec/spec.json"\n',
        encoding="utf-8",
    )

    with pytest.raises(pydantic.ValidationError, match="either application.python_spec"):
        application_module.Uptimely(tmp_path)

    config_path.write_text("[engine]\npreview_rows = 0\n", encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        application_module.Uptimely(tmp_path)


def test_project_named_config_requires_profile_and_rejects_config_path_conflict(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        application_module.Uptimely(tmp_path, config="prod")

    with pytest.raises(ValueError, match="cannot both"):
        application_module.Uptimely(tmp_path, config="prod", config_path=tmp_path / "config.toml")


def test_project_resolves_explicit_config_from_working_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "override.toml").write_text("[params]\nvalue = 7\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app = application_module.Uptimely(tmp_path / "other", config_path="override.toml")

    assert app.config_path == tmp_path / "override.toml"
    assert app.config.params.root == {"value": 7}


def test_project_rejects_bundle_from_different_project(
    app: application_module.Uptimely, tmp_path: pathlib.Path
) -> None:
    build = app.build()
    other_app = application_module.Uptimely(tmp_path / "other")
    with pytest.raises(ValueError, match="different project"):
        other_app.create_engine(build)


def test_project_builds_and_loads_fresh_bundles(app: application_module.Uptimely) -> None:
    first = app.build()
    loaded = app.load_build_bundle()
    assert first.project_root == app.root
    assert loaded is not first
    assert loaded.spec_definition.name == "First build"

    spec_path = app.root / application_module.SPEC_JSON_ENTRY_FILE
    spec_path.write_text('{"spec_version": 9, "name": "Second build"}', encoding="utf-8")
    second = app.build()

    assert second.spec_definition.name == "Second build"
    assert first.spec_definition.name == "First build"
    assert app.load_build_bundle().spec_definition.name == "Second build"
    assert not uptimely.Engine(second).run().failures


def test_run_forwards_options_and_holds_build_lock(app: application_module.Uptimely) -> None:
    app.build()
    src_path = pathlib.Path("custom-src")

    def run(
        runtime: uptimely.Engine,
        *,
        validate: bool,
        preview_rows: int,
        operator: tuple[str, str] | None,
        src_path: pathlib.Path | None,
    ) -> object:
        assert runtime.bundle.project_root == app.root
        assert (validate, preview_rows, operator, src_path) == (
            True,
            3,
            ("profile", "operator"),
            pathlib.Path("custom-src"),
        )
        with pytest.raises(application_module.BuildLockError):
            app.build()
        return mock.sentinel.result

    with mock.patch.object(uptimely.Engine, "run", autospec=True, side_effect=run):
        assert (
            app.run(
                validate=True, preview_rows=3, operator=("profile", "operator"), src_path=src_path
            )
            is mock.sentinel.result
        )

    app.build()


def test_run_uses_project_preview_and_bundled_source_by_default(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/spec.json").write_text(
        '{"spec_version": 9, "name": "Run config"}', encoding="utf-8"
    )
    (tmp_path / "custom-src").mkdir()
    (tmp_path / "uptimely.toml").write_text(
        '[application]\nsrc_path = "custom-src"\n[engine]\npreview_rows = 12\n',
        encoding="utf-8",
    )
    app = application_module.Uptimely(tmp_path)
    bundle = app.build()
    caplog.set_level(logging.DEBUG, logger="uptimely.engine.engine")

    with mock.patch.object(
        python_imports,
        "expose",
        wraps=python_imports.expose,
    ) as source_path:
        result = app.run()

    source_path.assert_called_once_with(app.root, src_path=bundle.package_paths["project"])
    assert (
        f"Selected Python source directory (bundle): {bundle.package_paths['project']}"
        in caplog.messages
    )
    assert not result.failures
    manifest_path = app.root / project_paths.RUN_MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["preview_rows"] == 12


def test_run_logs_resolved_source_override(
    app: application_module.Uptimely, caplog: pytest.LogCaptureFixture
) -> None:
    app.build()
    override = pathlib.Path("custom-src")
    (app.root / override).mkdir()
    caplog.set_level(logging.DEBUG, logger="uptimely.engine.engine")

    app.run(src_path=override)

    assert (
        f"Selected Python source directory (explicit override): {app.root / override}"
        in caplog.messages
    )


def test_run_reports_runtime_mismatches_before_exposing_code(
    app: application_module.Uptimely,
) -> None:
    (app.root / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=999"\n'
        'dependencies = ["uptimely-core>=999", "uptimely-test-nonexistent-dependency"]\n',
        encoding="utf-8",
    )
    app.build()

    with (
        mock.patch.object(python_imports, "expose") as expose,
        pytest.raises(ValueError, match="Python runtime preflight failed") as error,
    ):
        app.run()

    assert "does not satisfy >=999" in str(error.value)
    assert "does not satisfy uptimely-core>=999" in str(error.value)
    assert "Missing dependency: uptimely-test-nonexistent-dependency" in str(error.value)
    expose.assert_not_called()
    assert not (app.root / project_paths.RUN_MANIFEST_FILE).exists()


def test_run_ignores_dependencies_with_nonmatching_markers(
    app: application_module.Uptimely,
) -> None:
    (app.root / "pyproject.toml").write_text(
        '[project]\ndependencies = ["uptimely-core>=0", '
        "\"uptimely-test-nonexistent-dependency; python_version < '3'\"]\n",
        encoding="utf-8",
    )
    app.build()

    assert not app.run().failures


def test_run_releases_build_lock_on_failure(app: application_module.Uptimely) -> None:
    app.build()
    with (
        mock.patch.object(uptimely.Engine, "run", side_effect=ValueError("run failed")),
        pytest.raises(ValueError, match="run failed"),
    ):
        app.run()

    app.build()


def test_build_and_run_use_project_paths(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> None:
    root = example_project_factory(tmp_path / "example")
    app = uptimely.Uptimely(root)
    app.build(features=["health_signal_normalized"])

    result = app.run(validate=True, preview_rows=2)

    assert not result.failures
    assert ("pump", "health_signal_normalized") in result.calculated_outputs
    assert result.preview_frames["pump"].height == 2


def test_project_build_forwards_source_and_feature_options(
    app: application_module.Uptimely,
) -> None:
    source = app.root / application_module.SPEC_JSON_ENTRY_FILE
    with mock.patch.object(builder, "ProjectBuilder", autospec=True) as builder_class:
        result = app.build(
            python_spec="spec.spec:python_spec", json_spec=source, features=["reading"]
        )

    builder_class.assert_called_once_with(app.root)
    builder_class.return_value.build.assert_called_once_with(
        python_spec="spec.spec:python_spec",
        json_spec=source,
        features=["reading"],
        src_path=None,
        runtimes_path="runtimes",
    )
    assert result is builder_class.return_value.build.return_value


@pytest.mark.parametrize("validate", [False, True])
def test_project_load_forwards_validation(app: application_module.Uptimely, validate: bool) -> None:
    with mock.patch.object(bundle, "BundleStore", autospec=True) as store_class:
        result = app.load_build_bundle(validate=validate)

    store_class.assert_called_once_with(app.root)
    store_class.return_value.load.assert_called_once_with(validate=validate)
    assert result is store_class.return_value.load.return_value


@pytest.mark.parametrize("validate", [False, True])
def test_project_read_holds_and_releases_build_lock(
    app: application_module.Uptimely, validate: bool
) -> None:
    app.build()

    with app.read_build_bundle(validate=validate) as saved:
        assert saved.project_root == app.root
        assert saved.spec_definition.name == "First build"
        with pytest.raises(application_module.BuildLockError):
            app.build()

    assert app.build().spec_definition.name == "First build"


def test_project_load_reports_missing_build(app: application_module.Uptimely) -> None:
    with pytest.raises(application_module.BuildError):
        app.load_build_bundle()

    with pytest.raises(application_module.BuildError), app.read_build_bundle():
        pass

    with pytest.raises(application_module.BuildError):
        app.run()
