import dataclasses

import polars as pl
import pytest
from conftest import _spec_for_plan

from uptimely.compiler import plan as plan_module
from uptimely.engine import bindings as bindings_module
from uptimely.engine import state as state_module
from uptimely.spec import model as spec_model

PLAN = plan_module.ExecutionPlan.from_json("tests/fixtures/plans/simple_engine.json")


def _bindings(
    spec_definition: spec_model.Spec | None = None,
    state: state_module.RuntimeState | None = None,
    bind: dict[str, dict[str, dict[str, object]]] | None = None,
) -> bindings_module.RuntimeBindings:
    return bindings_module.RuntimeBindings(
        spec_definition or _spec_for_plan(PLAN),
        state or state_module.RuntimeState(),
        bind or {},
    )


def test_runtime_bindings_resolve_nested_runtime_values_and_dataframe_ids() -> None:
    dataset = pl.DataFrame({"asset_id": ["A"]})
    fragment = pl.DataFrame({"reading": [2]})
    state = state_module.RuntimeState(
        datasets={"telemetry": dataset},
        fragments={("telemetry", "reading"): fragment},
    )
    bindings = _bindings(
        state=state,
        bind={"storage": {"source": {"path": "/data/telemetry.parquet"}}},
    )

    assert bindings.resolve_value(
        {
            "dataset": ["telemetry"],
            "fragment": ["reading"],
            "paths": ["?storage.source.path"],
            "literal": [None, 1],
        },
        "object{str: array[string]}",
    ) == {
        "dataset": ["telemetry"],
        "fragment": ["reading"],
        "paths": ["/data/telemetry.parquet"],
        "literal": [None, 1],
    }
    assert bindings.resolve_value(
        {"frames": ["telemetry", "reading"]},
        "object{str: array[dataframe]}",
    ) == {"frames": [dataset, fragment]}


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("?", "Malformed runtime reference"),
        ("?storage.source", "Malformed runtime reference"),
        ("?unknown.source.path", "Unknown runtime namespace"),
        ("?storage.unknown.path", "Unknown storage object"),
        ("?storage.source.missing", "has no attribute"),
    ],
)
def test_runtime_bindings_reject_invalid_runtime_references(reference: str, message: str) -> None:
    bindings = _bindings(bind={"storage": {"source": {"path": "/data/input.parquet"}}})

    with pytest.raises(ValueError, match=message):
        bindings.resolve_runtime_reference(reference)


def test_runtime_bindings_reject_unavailable_dataframe_reference() -> None:
    bindings = _bindings()

    with pytest.raises(ValueError, match="Dataset dataframe is unavailable: missing"):
        bindings.resolve_value("missing", "dataframe")


def test_runtime_bindings_apply_spec_and_runtime_binding_overrides() -> None:
    spec_definition = _spec_for_plan(PLAN)
    spec_definition.functions["load"].args["source"].type = "array[string]"
    read_callable = dataclasses.replace(
        PLAN.callables[0], arguments={"source": ["?storage.source.path"]}
    )
    bindings = _bindings(
        spec_definition=spec_definition,
        bind={"storage": {"source": {"path": "/override/input.parquet"}}},
    )

    assert bindings.resolve_args(read_callable) == {"source": ["/override/input.parquet"]}


def test_runtime_bindings_reject_function_operation_mismatch() -> None:
    read_callable = dataclasses.replace(PLAN.callables[0], operation="write")
    bindings = _bindings()

    with pytest.raises(ValueError, match="does not match function load operation read"):
        bindings.resolve_args(read_callable)
