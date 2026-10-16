import ast
import dataclasses
import importlib
import pathlib
import subprocess
import sys

import pytest

import uptimely
from uptimely import analytics, entrypoint
from uptimely.analytics import model, resolved
from uptimely.analytics.json import codec
from uptimely.analytics.python import conversion, dataset, dimension, entity
from uptimely.compiler import compiler

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")


@pytest.mark.parametrize(
    "module",
    [
        "json_model",
        "json_model.analytics",
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
        importlib.import_module(f"uptimely.analytics.json.{module}")


def test_public_models_are_canonical_objects() -> None:
    assert uptimely.Analytics is analytics.Analytics is model.Analytics
    assert uptimely.Function is analytics.Function is resolved.Function
    assert uptimely.Call is analytics.Call is resolved.Call
    assert uptimely.PreparedAnalytics is analytics.PreparedAnalytics is resolved.PreparedAnalytics


def test_canonical_models_do_not_import_outer_layers() -> None:
    directory = pathlib.Path(model.__file__).parent
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level < 2, path
                if node.module == "uptimely":
                    assert {alias.name for alias in node.names} <= {"contracts", "row_context"}
                else:
                    assert not (node.module or "").startswith("uptimely"), path
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith("uptimely") for alias in node.names), path


@pytest.mark.parametrize(
    "module",
    [
        "uptimely.analytics.model.analytics",
        "uptimely.analytics.resolved",
        "uptimely.analytics.python.conversion",
        "uptimely.analytics.json.codec",
        "uptimely.analytics.api",
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


def test_json_round_trip_preserves_the_document_and_prepared_analysis(
    tmp_path: pathlib.Path,
) -> None:
    original_document = codec.load_document(ANALYTICS_PATH)
    document = analytics.load_analytics(ANALYTICS_PATH)
    prepared = analytics.prepare_analytics(document)
    expected = codec.to_document(document)
    path = tmp_path / "nested" / "analytics.json"

    assert codec.write_document(document, path) == str(path)
    assert codec.load_document(path) == expected == original_document
    assert prepared.document is document
    assert not {"path", "calls", "resolved_functions"} & model.Analytics.model_fields.keys()
    assert not {"path", "calls", "resolved_functions"} & expected.keys()

    reloaded = analytics.load_analytics(path)
    assert analytics.prepare_analytics(reloaded) == prepared
    first = compiler.Compiler(document).compile()
    second = compiler.Compiler(reloaded).compile()
    assert first.plan.resources == second.plan.resources
    assert {
        item.id: dataclasses.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in first.callables
    } == {
        item.id: dataclasses.replace(item, dependency_ids=sorted(item.dependency_ids))
        for item in second.callables
    }
    assert [set(stage) for stage in first.plan.stages] == [
        set(stage) for stage in second.plan.stages
    ]


def test_codec_preserves_function_descriptions_and_dataset_ids() -> None:
    document = model.Analytics.model_validate(
        {
            "functions": {
                "collapse": {
                    "operation": "collapse",
                    "returns": "dataframe",
                    "entrypoint": "not_installed:collapse",
                    "args": {"dataset": {"type": "dataframe"}},
                },
            },
            "entities": {
                "assets": {
                    "name": "Assets",
                    "datasets": [{"id": "first"}, {"id": "second"}],
                }
            },
        }
    )

    payload = codec.to_document(document)

    assert payload["functions"]["collapse"]["description"] is None
    assert [item["id"] for item in payload["entities"]["assets"]["datasets"]] == [
        "first",
        "second",
    ]
    assert "id" not in payload["entities"]["assets"]
    assert "id" not in payload["functions"]["collapse"]["args"]["dataset"]
    assert model.Analytics.model_validate(payload) == document


def test_structural_operations_do_not_inspect_python_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_inspection(*args: object, **kwargs: object) -> None:
        pytest.fail("Structural operations must not inspect Python entrypoints")

    monkeypatch.setattr(entrypoint, "read_signature", unexpected_inspection)
    payload = codec.load_document(ANALYTICS_PATH)
    document = model.Analytics.model_validate(payload)

    assert codec.to_document(document) == payload
    converted = conversion.to_model(
        entities=[entity.Entity(id="assets", name="Assets", dimensions=[], datasets=[])]
    )
    assert converted.entities["assets"].name == "Assets"
    assert analytics.prepare_analytics(document).calls
    assert analytics.load_analytics(ANALYTICS_PATH) == document


def test_preparation_does_not_mutate_the_document() -> None:
    document = model.Analytics.model_validate(codec.load_document(ANALYTICS_PATH))
    before = codec.to_document(document)

    prepared = analytics.prepare_analytics(document)

    assert prepared.functions
    assert prepared.calls
    assert codec.to_document(document) == before
    assert all(
        call is next(item for item in prepared.calls if item.feature == call.feature)
        for function in prepared.functions
        for call in function.callables
    )


def test_python_dictionary_and_json_export_share_the_same_encoding(
    tmp_path: pathlib.Path,
) -> None:
    pump = dimension.Dimension(id="pump", type="string")
    declaration = analytics.PythonAnalytics(
        entities=[
            entity.Entity(
                id="assets",
                name="Assets",
                dimensions=[pump],
                datasets=[dataset.Dataset(id="readings")],
            )
        ],
        dimensions=[pump],
    )
    document = declaration.to_model()
    path = tmp_path / "analytics.json"
    codec.write_document(document, path)

    assert declaration.to_dict() == codec.to_document(document) == codec.load_document(path)
    assert declaration.to_dict()["name"] is None
    assert "id" not in declaration.to_dict()["entities"]["assets"]
