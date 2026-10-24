import pathlib

import pytest

from uptimely import project, spec
from uptimely.project.build import source as build_source

FIXTURE_SPEC = pathlib.Path(__file__).parents[1] / "fixtures/spec/observation_totals.json"


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


def test_python_source_loads_explicit_entrypoint_with_module_api(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = f"custom_project_spec_{tmp_path.name.replace('-', '_')}"
    dependency_name = f"custom_project_dependency_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{dependency_name}.py").write_text(
        "VALUE = 'Custom project spec'\n", encoding="utf-8"
    )
    (tmp_path / f"{module_name}.py").write_text(
        f"import {dependency_name}\n"
        "from uptimely.spec.python.entity import Entity\n"
        "from uptimely.spec.python.spec import PythonSpec\n"
        f"python_spec = PythonSpec(name={dependency_name}.VALUE, datasets={{"
        "Entity(id='assets', name='Assets', dimensions=[]): []})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    loaded = build_source.PythonSource(tmp_path, f"{module_name}:python_spec").load()

    assert isinstance(loaded, spec.Spec)
    assert loaded.entities["assets"].name == "Assets"
    assert loaded.name == "Custom project spec"
