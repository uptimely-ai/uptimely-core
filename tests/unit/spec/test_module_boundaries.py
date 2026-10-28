import ast
import dataclasses
import importlib
import pathlib
import subprocess
import sys

import pytest
from conftest import EXAMPLES_ROOT

import uptimely
from uptimely import entrypoint, spec
from uptimely.compiler import compiler
from uptimely.execution_plan import models as execution_plan_models
from uptimely.spec import model, validation
from uptimely.spec.json import codec
from uptimely.spec.python import conversion, dataset, dimension, entity

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


@pytest.mark.parametrize(
    "module",
    [
        "json_model",
        "json_model.spec",
        "json_model.common",
        "json_model.dataset",
        "json_model.functions",
        "json_model.resolved",
        "json_parser",
        "json_serializer",
        "catalog",
        "bindings",
        "json_functions",
    ],
)
def test_removed_json_module_paths_are_unavailable(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"uptimely.spec.json.{module}")


def test_public_models_are_canonical_objects() -> None:
    assert uptimely.Spec is spec.Spec is model.Spec


@pytest.mark.parametrize("name", ["Function", "Call", "PreparedSpec", "prepare_spec"])
def test_removed_prepared_spec_exports_are_unavailable(name: str) -> None:
    assert not hasattr(uptimely, name)
    assert not hasattr(spec, name)


@pytest.mark.parametrize("module", ["resolved", "resolution"])
def test_removed_prepared_spec_modules_are_unavailable(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"uptimely.spec.{module}")


def test_canonical_models_do_not_import_outer_layers() -> None:
    directory = pathlib.Path(model.__file__).parent
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level < 2, path
                if node.module == "uptimely":
                    assert {alias.name for alias in node.names} <= {"row_context"}
                elif node.module == "uptimely.spec":
                    assert {alias.name for alias in node.names} <= {"functions", "selectors"}
                else:
                    assert not (node.module or "").startswith("uptimely"), path
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith("uptimely") for alias in node.names), path


def test_compiler_does_not_import_presentation_or_runtime_layers() -> None:
    directory = pathlib.Path(compiler.__file__).parent
    for path in directory.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(("uptimely.explorer", "uptimely.engine"))
                    for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                if node.module == "uptimely":
                    assert not {"explorer", "engine"} & {alias.name for alias in node.names}, path
                assert not (node.module or "").startswith(
                    ("uptimely.explorer", "uptimely.engine")
                ), path


def test_execution_plan_does_not_import_outer_layers() -> None:
    directory = pathlib.Path(execution_plan_models.__file__).parent
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(
                        (
                            "uptimely.compiler",
                            "uptimely.engine",
                            "uptimely.explorer",
                            "uptimely.project",
                        )
                    )
                    for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    (
                        "uptimely.compiler",
                        "uptimely.engine",
                        "uptimely.explorer",
                        "uptimely.project",
                    )
                ), path


@pytest.mark.parametrize(
    "module",
    [
        "uptimely.spec.model.spec",
        "uptimely.spec.validation",
        "uptimely.spec.validation.mapping_outputs",
        "uptimely.spec.validation.mapping_inputs",
        "uptimely.spec.validation.mapping_contracts",
        "uptimely.spec.validation.dependencies",
        "uptimely.spec.python.conversion",
        "uptimely.spec.json.codec",
        "uptimely.spec.api",
        "uptimely.compiler.graph",
        "uptimely.compiler.compiler",
    ],
)
def test_modules_import_in_a_fresh_process(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import importlib; importlib.import_module({module!r})"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "modules",
    [
        ("uptimely.project", "uptimely.explorer.explorer"),
        ("uptimely.explorer.explorer", "uptimely.project"),
        ("uptimely.project.build.builder", "uptimely.explorer.explorer"),
        ("uptimely.explorer.explorer", "uptimely.project.build.builder"),
    ],
)
def test_project_and_explorer_import_in_either_order_in_a_fresh_process(
    modules: tuple[str, str],
) -> None:
    script = f"""
import importlib
for name in {modules!r}:
    importlib.import_module(name)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_json_round_trip_preserves_the_document_and_compiled_plan(
    tmp_path: pathlib.Path,
) -> None:
    original_document = codec.load_document(SPEC_PATH)
    document = spec.load_spec(SPEC_PATH)
    expected = codec.to_document(document)
    path = tmp_path / "nested" / "spec.json"

    assert codec.write_document(document, path) == str(path)
    assert codec.load_document(path) == expected == original_document
    assert not {"path", "calls", "resolved_functions"} & model.Spec.model_fields.keys()
    assert not {"path", "calls", "resolved_functions"} & expected.keys()

    reloaded = spec.load_spec(path)
    assert reloaded == document
    first = compiler.Compiler().compile(document)
    second = compiler.Compiler().compile(reloaded)
    assert first.resources == second.resources
    assert {
        item.id: dataclasses.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in first.invocations
    } == {
        item.id: dataclasses.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in second.invocations
    }
    assert [set(stage) for stage in first.stages] == [set(stage) for stage in second.stages]


def test_codec_preserves_function_descriptions_and_dataset_ids() -> None:
    document = model.Spec.model_validate(
        {
            "functions": {
                "collapse": {
                    "kind": "collapse",
                    "returns": "dataframe",
                    "entrypoint": "not_installed:collapse",
                    "args": {"dataset": {"type": "dataframe"}},
                },
            },
            "entities": {
                "assets": {
                    "name": "Assets",
                    "datasets": {"first": {}, "second": {}},
                }
            },
        }
    )

    payload = codec.to_document(document)

    assert payload["functions"]["collapse"]["description"] is None
    assert list(payload["entities"]["assets"]["datasets"]) == [
        "first",
        "second",
    ]
    assert "id" not in payload["entities"]["assets"]
    assert "id" not in payload["functions"]["collapse"]["args"]["dataset"]
    assert model.Spec.model_validate(payload) == document


def test_structural_operations_do_not_inspect_python_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_inspection(*args: object, **kwargs: object) -> None:
        pytest.fail("Structural operations must not inspect Python entrypoints")

    monkeypatch.setattr(entrypoint, "Entrypoint", unexpected_inspection)
    payload = codec.load_document(SPEC_PATH)
    document = model.Spec.model_validate(payload)

    assert codec.to_document(document) == payload
    converted = conversion.to_model(
        entities=[entity.Entity(id="assets", name="Assets", dimensions=[], datasets=[])]
    )
    assert converted.entities["assets"].name == "Assets"
    validation.validate_spec(document)
    graph = spec.FeatureGraph(document)
    assert graph.feature_names
    assert all(function is document.functions[function.id] for function in graph.functions)
    assert spec.load_spec(SPEC_PATH) == document


def test_validation_does_not_mutate_the_document() -> None:
    document = model.Spec.model_validate(codec.load_document(SPEC_PATH))
    before = codec.to_document(document)

    validation.validate_spec(document)

    assert codec.to_document(document) == before


def test_python_dictionary_and_json_export_share_the_same_encoding(
    tmp_path: pathlib.Path,
) -> None:
    pump = dimension.Dimension(id="pump", type="string")
    assets = entity.Entity(id="assets", name="Assets", dimensions=[pump])

    class Readings(dataset.Dataset):
        id = "readings"
        entity = assets

    declaration = spec.PythonSpec(dimensions=[pump], entities=[assets], datasets=[Readings])
    document = declaration.to_model()
    path = tmp_path / "spec.json"
    codec.write_document(document, path)

    assert declaration.to_dict() == codec.to_document(document) == codec.load_document(path)
    assert declaration.to_dict()["name"] is None
    assert "id" not in declaration.to_dict()["entities"]["assets"]
