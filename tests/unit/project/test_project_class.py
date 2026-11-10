"""Tests for root-bound project operations."""

import pathlib
from unittest import mock

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
    with mock.patch.object(builder, "build", autospec=True) as build:
        result = project.build(
            python_spec="spec.spec:python_spec", json_spec=source, features=["reading"]
        )

    build.assert_called_once_with(
        project.root,
        python_spec="spec.spec:python_spec",
        json_spec=source,
        features=["reading"],
    )
    assert result is build.return_value


@pytest.mark.parametrize("validate", [False, True])
def test_project_load_forwards_validation(project: project_module.Project, validate: bool) -> None:
    with mock.patch.object(bundle, "load_build_bundle", autospec=True) as load:
        result = project.load_build_bundle(validate=validate)

    load.assert_called_once_with(project.root, validate=validate)
    assert result is load.return_value


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
