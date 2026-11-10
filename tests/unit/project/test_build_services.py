"""Tests for reusable root-bound build and bundle services."""

import pathlib
import shutil

import pytest

from uptimely import project
from uptimely.project.build import builder, bundle


def test_build_services_resolve_root_once(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    monkeypatch.chdir(tmp_path)
    project_builder = builder.ProjectBuilder("project")
    store = bundle.BundleStore("project")
    monkeypatch.chdir(tmp_path.parent)

    assert project_builder.root == root
    assert store.root == root
    assert not root.exists()


def test_builder_and_store_can_be_reused_after_failed_build(tmp_path: pathlib.Path) -> None:
    spec_path = tmp_path / project.SPEC_JSON_ENTRY_FILE
    spec_path.parent.mkdir()
    spec_path.write_text('{"spec_version": 8, "name": "First build"}', encoding="utf-8")
    project_builder = builder.ProjectBuilder(tmp_path)
    store = bundle.BundleStore(tmp_path)
    first = project_builder.build()
    assert store.load().spec_definition.name == "First build"

    with pytest.raises(project.ProjectBuildError, match="feature selection"):
        project_builder.build(features=[])
    assert store.load().spec_definition.name == "First build"

    spec_path.write_text('{"spec_version": 8, "name": "Second build"}', encoding="utf-8")
    second = project_builder.build()
    assert second.spec_definition.name == "Second build"
    assert second.manifest.features is None
    assert first.spec_definition.name == "First build"

    with store.read() as saved:
        assert saved.spec_definition.name == "Second build"
        with pytest.raises(project.BuildLockError):
            project_builder.build()
    assert project_builder.build().spec_definition.name == "Second build"


def test_store_loads_staged_bundle_under_existing_lock(tmp_path: pathlib.Path) -> None:
    spec_path = tmp_path / project.SPEC_JSON_ENTRY_FILE
    spec_path.parent.mkdir()
    spec_path.write_text('{"spec_version": 8, "name": "Active build"}', encoding="utf-8")
    active = builder.ProjectBuilder(tmp_path).build()
    staging_root = tmp_path / project.GENERATED_DIR / "staged"
    shutil.copytree(active.root, staging_root)
    (staging_root / "spec.json").write_text(
        '{"spec_version": 8, "name": "Staged build"}', encoding="utf-8"
    )
    store = bundle.BundleStore(tmp_path)

    with project.build_lock(tmp_path, exclusive=True, wait=False):
        staged = store.load_at(staging_root, validate=False, log_structure=False)

    assert staged.root == staging_root
    assert staged.project_root == tmp_path
    assert staged.spec_definition.name == "Staged build"
    assert store.load().spec_definition.name == "Active build"
