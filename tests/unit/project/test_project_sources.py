import logging
import pathlib
from unittest import mock

import pytest

from uptimely import project, spec
from uptimely.project.build import builder
from uptimely.project.build import source as build_source
from uptimely.spec import validation

FIXTURE_SPEC = pathlib.Path(__file__).parents[2] / "fixtures/spec/observation_totals.json"


def test_json_source_loads_configured_path(tmp_path: pathlib.Path) -> None:
    configured_path = tmp_path / "custom-spec.json"
    configured_path.write_bytes(FIXTURE_SPEC.read_bytes())
    source = build_source.JsonSource(tmp_path, configured_path)

    assert source.path == configured_path
    assert source.is_available()
    assert source.load() == spec.load_spec(FIXTURE_SPEC)


def test_spec_source_loads_explicit_json_without_default_source(tmp_path: pathlib.Path) -> None:
    configured_path = tmp_path / "custom-spec.json"
    configured_path.write_bytes(FIXTURE_SPEC.read_bytes())

    loaded = build_source.SpecSource(tmp_path).load(json_spec=configured_path)

    assert loaded == spec.load_spec(FIXTURE_SPEC)


def test_spec_source_discovers_conventional_json_source(tmp_path: pathlib.Path) -> None:
    configured_path = tmp_path / project.SPEC_JSON_ENTRY_FILE
    configured_path.parent.mkdir(parents=True)
    configured_path.write_bytes(FIXTURE_SPEC.read_bytes())

    loaded = build_source.SpecSource(tmp_path).load()

    assert loaded == spec.load_spec(FIXTURE_SPEC)


def test_spec_source_resolves_without_loading(tmp_path: pathlib.Path) -> None:
    python_path = tmp_path / project.SPEC_PYTHON_ENTRY_FILE
    python_path.parent.mkdir(parents=True)
    python_path.write_text("raise RuntimeError('Source must not be loaded')\n", encoding="utf-8")
    source = build_source.SpecSource(tmp_path).resolve()

    assert isinstance(source, build_source.PythonSource)
    assert source.path == python_path
    assert source.entrypoint.module.location == "spec.spec"
    assert source.entrypoint.function.name == project.DEFAULT_SPEC_ATTRIBUTE


def test_python_spec_rejects_local_file_entrypoints(tmp_path: pathlib.Path) -> None:
    python_path = tmp_path / project.SPEC_PYTHON_ENTRY_FILE
    python_path.parent.mkdir(parents=True)
    python_path.write_text("python_spec = None\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid module path"):
        build_source.PythonSource(tmp_path, f"{python_path}:python_spec")


def test_spec_source_rejects_ambiguous_discovered_sources(tmp_path: pathlib.Path) -> None:
    python_path = tmp_path / project.SPEC_PYTHON_ENTRY_FILE
    python_path.parent.mkdir(parents=True)
    python_path.write_text("python_spec = None\n", encoding="utf-8")
    json_path = tmp_path / project.SPEC_JSON_ENTRY_FILE
    json_path.write_bytes(FIXTURE_SPEC.read_bytes())

    with pytest.raises(ValueError, match="Ambiguous spec sources") as error:
        build_source.SpecSource(tmp_path).load()
    assert "--python-spec" not in str(error.value)
    assert "--json-spec" not in str(error.value)


def test_spec_source_missing_source_error_is_not_cli_specific(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError, match="No spec source found") as error:
        build_source.SpecSource(tmp_path).load()

    assert "--python-spec" not in str(error.value)
    assert "--json-spec" not in str(error.value)


@pytest.mark.parametrize("validate", [False, True])
def test_python_source_loads_explicit_entrypoint_with_module_api(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, validate: bool
) -> None:
    module_name = f"custom_project_spec_{tmp_path.name.replace('-', '_')}"
    dependency_name = f"custom_project_dependency_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{dependency_name}.py").write_text(
        "VALUE = 'Custom project spec'\n", encoding="utf-8"
    )
    (tmp_path / f"{module_name}.py").write_text(
        f"import {dependency_name}\n"
        "from uptimely.spec.python import Profile\n"
        "from uptimely.spec.python.spec import Spec\n"
        "class Values(Profile):\n"
        "    id = 'values'\n"
        f"python_spec = Spec(profiles=[Values], "
        f"name={dependency_name}.VALUE)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with mock.patch.object(validation, "validate_spec", wraps=validation.validate_spec) as check:
        loaded = build_source.SpecSource(tmp_path).load(
            python_spec=f"{module_name}:python_spec", validate=validate
        )
    assert check.call_count == int(validate)

    assert isinstance(loaded, spec.Spec)
    assert list(loaded.profiles) == ["values"]
    assert loaded.name == "Custom project spec"


@pytest.mark.parametrize("validate", [False, True])
def test_json_source_forwards_validation_option(tmp_path: pathlib.Path, validate: bool) -> None:
    with mock.patch.object(validation, "validate_spec", wraps=validation.validate_spec) as check:
        project.load_spec_source(None, tmp_path, FIXTURE_SPEC, validate=validate)

    assert check.call_count == int(validate)


@pytest.mark.parametrize("source_kind", ["json", "python"])
def test_build_defers_source_semantic_validation_to_compiler(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, source_kind: str
) -> None:
    module_name = f"deferred_validation_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{module_name}.py").write_text(
        "from uptimely.spec.python import Spec, Profile\n"
        "values = Profile(id='values')\n"
        "python_spec = Spec(profiles=[values])\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    json_path = tmp_path / "spec.json"
    json_path.write_text('{"spec_version": 4}', encoding="utf-8")
    python_spec = f"{module_name}:python_spec" if source_kind == "python" else None
    json_spec = json_path if source_kind == "json" else None

    with mock.patch.object(validation, "validate_spec", wraps=validation.validate_spec) as check:
        document = builder._load_spec_definition(tmp_path, python_spec, json_spec)
        check.assert_not_called()
        builder._compile_plan(document, None)
        check.assert_called_once_with(document)


def test_build_reports_deferred_semantic_error_at_compilation(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "spec.json"
    path.write_text(
        (
            '{"dimensions": {"child": {"resolutions": {"default": '
            '{"key": "child", "type": "integer", "parent": "missing"}}}}}'
        ),
        encoding="utf-8",
    )
    document = builder._load_spec_definition(tmp_path, None, path)

    with pytest.raises(project.ProjectBuildError, match="compilation.*unknown parent"):
        builder._compile_plan(document, None)


def test_complete_build_validates_spec_semantics_once(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"spec_version": 4}', encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="uptimely")

    with mock.patch.object(validation, "validate_spec", wraps=validation.validate_spec) as check:
        bundle = project.build_project(tmp_path, json_spec=path)

    check.assert_called_once()
    assert caplog.messages.count("\nSpec validation:\n  Document structure:") == 1
    assert bundle.spec_path.is_file()
    assert (tmp_path / project.EXPLORER_DATA_FILE).is_file()
    assert project.load_build_bundle(tmp_path).spec_definition == bundle.spec_definition
