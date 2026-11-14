"""Tests for root-bound project operations."""

import pathlib
from unittest import mock

import pydantic
import pytest

import uptimely
from uptimely import project as project_module
from uptimely.project.build import builder, bundle


@pytest.fixture
def project(tmp_path: pathlib.Path) -> project_module.Project:
    """Create a project with a minimal discoverable source Spec."""
    spec_path = tmp_path / project_module.SPEC_JSON_ENTRY_FILE
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text('{"spec_version": 8, "name": "First build"}', encoding="utf-8")
    return project_module.Project(tmp_path)


def test_project_is_exported_from_package() -> None:
    assert uptimely.Project is project_module.Project


@pytest.mark.parametrize("root", [None, "", ".", pathlib.Path(".")])
def test_project_resolves_root_at_construction(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, root: str | pathlib.Path | None
) -> None:
    monkeypatch.chdir(tmp_path)
    project = uptimely.Project() if root is None else uptimely.Project(root)
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)

    assert project.root == tmp_path.resolve()
    assert not (tmp_path / project_module.GENERATED_DIR).exists()


def test_project_loads_and_passes_config_to_engine(tmp_path: pathlib.Path) -> None:
    config_path = tmp_path / "uptimely.toml"
    config_path.write_text(
        '[engine.backend]\ndataframe = "POLARS"\nevaluation = "lazy"\n'
        '[paths]\nsource = "data/source.csv"\n[params]\nthreshold = 42\n',
        encoding="utf-8",
    )
    instance = project_module.Project(tmp_path)
    config_path.write_text("[params]\nthreshold = 99\n", encoding="utf-8")
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/spec.json").write_text(
        '{"spec_version": 8, "name": "Config test"}', encoding="utf-8"
    )

    runtime = instance.create_engine(instance.build())

    assert runtime.config.backend.dataframe == "POLARS"
    assert runtime.config.backend.evaluation == "lazy"
    assert runtime.parameters == {"threshold": 42}
    assert runtime.paths == {"source": "data/source.csv"}
    assert project_module.Project(tmp_path).config.params.root == {"threshold": 99}


def test_project_explicit_config_and_failures(tmp_path: pathlib.Path) -> None:
    (tmp_path / "uptimely.toml").write_text("[params]\nvalue = 1\n", encoding="utf-8")
    override = tmp_path / "other.toml"
    override.write_text("[params]\nvalue = 2\n", encoding="utf-8")
    assert project_module.Project(tmp_path, config_path=override).config.params.root == {"value": 2}

    with pytest.raises(FileNotFoundError):
        project_module.Project(tmp_path, config_path=tmp_path / "missing.toml")
    override.write_text("[params]\nvalue = [1]\n", encoding="utf-8")
    with pytest.raises(pydantic.ValidationError):
        project_module.Project(tmp_path, config_path=override)


def test_project_resolves_explicit_config_from_working_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "override.toml").write_text("[params]\nvalue = 7\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    instance = project_module.Project(tmp_path / "other", config_path="override.toml")

    assert instance.config_path == tmp_path / "override.toml"
    assert instance.config.params.root == {"value": 7}


def test_project_rejects_bundle_from_different_project(
    project: project_module.Project, tmp_path: pathlib.Path
) -> None:
    build = project.build()
    other = project_module.Project(tmp_path / "other")
    with pytest.raises(ValueError, match="different project"):
        other.create_engine(build)


def test_project_builds_and_loads_fresh_bundles(project: project_module.Project) -> None:
    first = project.build()
    loaded = project.load_build_bundle()
    assert first.project_root == project.root
    assert loaded is not first
    assert loaded.spec_definition.name == "First build"

    spec_path = project.root / project_module.SPEC_JSON_ENTRY_FILE
    spec_path.write_text('{"spec_version": 8, "name": "Second build"}', encoding="utf-8")
    second = project.build()

    assert second.spec_definition.name == "Second build"
    assert first.spec_definition.name == "First build"
    assert project.load_build_bundle().spec_definition.name == "Second build"
    assert not uptimely.Engine(second).run().failures


def test_project_build_forwards_source_and_feature_options(
    project: project_module.Project,
) -> None:
    source = project.root / project_module.SPEC_JSON_ENTRY_FILE
    with mock.patch.object(builder, "ProjectBuilder", autospec=True) as builder_class:
        result = project.build(
            python_spec="spec.spec:python_spec", json_spec=source, features=["reading"]
        )

    builder_class.assert_called_once_with(project.root)
    builder_class.return_value.build.assert_called_once_with(
        python_spec="spec.spec:python_spec",
        json_spec=source,
        features=["reading"],
        src_path=None,
    )
    assert result is builder_class.return_value.build.return_value


@pytest.mark.parametrize("validate", [False, True])
def test_project_load_forwards_validation(project: project_module.Project, validate: bool) -> None:
    with mock.patch.object(bundle, "BundleStore", autospec=True) as store_class:
        result = project.load_build_bundle(validate=validate)

    store_class.assert_called_once_with(project.root)
    store_class.return_value.load.assert_called_once_with(validate=validate)
    assert result is store_class.return_value.load.return_value


@pytest.mark.parametrize("validate", [False, True])
def test_project_read_holds_and_releases_build_lock(
    project: project_module.Project, validate: bool
) -> None:
    project.build()

    with project.read_build_bundle(validate=validate) as saved:
        assert saved.project_root == project.root
        assert saved.spec_definition.name == "First build"
        with pytest.raises(project_module.BuildLockError):
            project.build()

    assert project.build().spec_definition.name == "First build"


def test_project_load_reports_missing_build(project: project_module.Project) -> None:
    with pytest.raises(project_module.BuildError):
        project.load_build_bundle()

    with pytest.raises(project_module.BuildError), project.read_build_bundle():
        pass
