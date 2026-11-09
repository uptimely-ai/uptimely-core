import ast
import copy
import pathlib
import subprocess
import sys

import pytest
from support import examples as example_support

import uptimely
from uptimely import entrypoint, spec
from uptimely.compiler import compiler
from uptimely.plan import models as execution_plan_models
from uptimely.spec import model, serialization, validation
from uptimely.spec.python import conversion, dimension, profile

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_public_models_are_canonical_objects() -> None:
    assert spec.Spec is model.Spec
    assert uptimely.Spec is not model.Spec


def test_canonical_models_do_not_import_outer_layers() -> None:
    directory = pathlib.Path(model.__file__).parent
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level < 2, path
                if node.module == "uptimely":
                    assert not {alias.name for alias in node.names}
                elif node.module == "uptimely.spec":
                    allowed_imports = {
                        "arg_types",
                        "function_kinds",
                        "row_context",
                        "selectors",
                    }
                    if path.name == "spec.py":
                        allowed_imports.add("merge")
                    assert {alias.name for alias in node.names} <= allowed_imports
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


def test_graph_does_not_import_explorer() -> None:
    directory = pathlib.Path(spec.__file__).parent / "graph"
    for path in directory.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("uptimely.explorer") for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("uptimely.explorer"), path


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
        "uptimely.spec.function_kinds",
        "uptimely.spec.validation",
        "uptimely.spec.validation.rules.operators.outputs",
        "uptimely.spec.validation.rules.operators.inputs",
        "uptimely.spec.validation.rules.operators.contracts",
        "uptimely.spec.validation.rules.operators.dependencies",
        "uptimely.spec.python.conversion",
        "uptimely.spec.serialization",
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
        ("uptimely.project", "uptimely.explorer.presentation"),
        ("uptimely.explorer.presentation", "uptimely.project"),
        ("uptimely.project.build.builder", "uptimely.explorer.presentation"),
        ("uptimely.explorer.presentation", "uptimely.project.build.builder"),
    ],
)
def test_project_and_explorer_presentation_import_in_either_order_in_a_fresh_process(
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


@pytest.mark.usefixtures("example_projects")
def test_json_round_trip_preserves_the_document_and_compiled_plan(
    tmp_path: pathlib.Path,
) -> None:
    original_document = serialization.load_document(SPEC_PATH)
    document = spec.load_spec(SPEC_PATH)
    expected = serialization.to_document(document)
    path = tmp_path / "nested" / "spec.json"

    assert serialization.write_document(document, path) == str(path)
    assert serialization.load_document(path) == expected == original_document
    assert not {"path", "calls", "resolved_functions"} & model.Spec.model_fields.keys()
    assert not {"path", "calls", "resolved_functions"} & expected.keys()

    reloaded = spec.load_spec(path)
    assert reloaded == document
    first = compiler.Compiler().compile(document)
    second = compiler.Compiler().compile(reloaded)
    assert {
        item.id: copy.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in first.invocations
    } == {
        item.id: copy.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in second.invocations
    }
    assert [set(stage) for stage in first.stages] == [set(stage) for stage in second.stages]


def test_serialization_preserves_function_descriptions_and_profile_ids() -> None:
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
            "profiles": {"first": {}, "second": {}},
        }
    )

    payload = serialization.to_document(document)

    assert payload["functions"]["collapse"]["description"] is None
    assert list(payload["profiles"]) == ["first", "second"]
    assert all("id" not in profile for profile in payload["profiles"].values())
    assert "id" not in payload["functions"]["collapse"]["args"]["dataset"]
    assert model.Spec.model_validate(payload) == document


@pytest.mark.usefixtures("example_projects")
def test_structural_operations_do_not_inspect_python_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_inspection(*args: object, **kwargs: object) -> None:
        pytest.fail("Structural operations must not inspect Python entrypoints")

    monkeypatch.setattr(entrypoint, "Entrypoint", unexpected_inspection)
    payload = serialization.load_document(SPEC_PATH)
    document = model.Spec.model_validate(payload)

    assert serialization.to_document(document) == payload
    converted = conversion.to_model(profiles=[profile.Profile(id="assets")])
    assert converted.profiles["assets"].name == "Assets"
    validation.validate_spec(document)
    graph = spec.FeatureGraph(document)
    assert graph.feature_names
    expected_operators = list(document.operators)
    assert all(
        actual is expected
        for actual, expected in zip(graph.operators, expected_operators, strict=True)
    )
    assert spec.load_spec(SPEC_PATH) == document


@pytest.mark.usefixtures("example_projects")
def test_validation_does_not_mutate_the_document() -> None:
    document = model.Spec.model_validate(serialization.load_document(SPEC_PATH))
    before = serialization.to_document(document)

    validation.validate_spec(document)

    assert serialization.to_document(document) == before


def test_python_dictionary_and_json_export_share_the_same_encoding(
    tmp_path: pathlib.Path,
) -> None:
    pump = dimension.Dimension(
        id="pump",
        resolutions=[dimension.Resolution(id="machine", key="pump_id", type="string")],
    )

    class Readings(profile.Profile):
        id = "readings"
        grain = [pump.resolution("machine")]

    declaration = uptimely.Spec(profiles=[Readings])
    document = declaration.to_model()
    path = tmp_path / "spec.json"
    serialization.write_document(document, path)

    assert (
        declaration.to_dict()
        == serialization.to_document(document)
        == serialization.load_document(path)
    )
    assert declaration.to_dict()["name"] is None
    assert "id" not in declaration.to_dict()["profiles"]["readings"]
