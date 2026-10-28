import dataclasses

import polars as pl
import pytest
from conftest import _spec_for_plan

from uptimely import execution_plan as plan_module
from uptimely.engine import bindings as bindings_module
from uptimely.engine import config as config_module
from uptimely.engine import state as state_module
from uptimely.spec import model as spec_model

PLAN = plan_module.from_json("tests/fixtures/plans/simple_engine.json")


def _bindings(
    spec_definition: spec_model.Spec | None = None,
    state: state_module.RuntimeState | None = None,
    parameters: dict[str, object] | None = None,
) -> bindings_module.RuntimeBindings:
    return bindings_module.RuntimeBindings(
        spec_definition or _spec_for_plan(PLAN),
        state or state_module.RuntimeState(),
        parameters or {},
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
        parameters={"telemetry_source": "/data/telemetry.parquet", "null_value": None},
    )

    assert bindings.resolve_value(
        {
            "dataset": ["telemetry"],
            "fragment": ["reading"],
            "paths": ["$params.telemetry_source"],
            "nested": {"nullable": "$params.null_value"},
            "literal": [None, 1],
        },
        "object{str: array[string]}",
    ) == {
        "dataset": ["telemetry"],
        "fragment": ["reading"],
        "paths": ["/data/telemetry.parquet"],
        "nested": {"nullable": None},
        "literal": [None, 1],
    }
    assert bindings.resolve_value(
        {"frames": ["telemetry", "reading"]},
        "object{str: array[dataframe]}",
    ) == {"frames": [dataset, fragment]}


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("$params.", "Malformed parameter reference"),
        ("$params.source.path", "Malformed parameter reference"),
        ("$params.unknown", "Unresolved parameter"),
    ],
)
def test_runtime_bindings_reject_invalid_runtime_references(reference: str, message: str) -> None:
    bindings = _bindings(parameters={"source": "/data/input.parquet"})

    with pytest.raises(ValueError, match=message):
        bindings.resolve_parameter_reference(reference)


def test_runtime_bindings_reject_unavailable_dataframe_reference() -> None:
    bindings = _bindings()

    with pytest.raises(ValueError, match="Dataset dataframe is unavailable: missing"):
        bindings.resolve_value("missing", "dataframe")


def test_parameter_config_accepts_only_flat_scalar_values() -> None:
    config = config_module.ParameterConfig.model_validate(
        {"limit": 1.5, "enabled": True, "empty": None, "path": "data/input.json"}
    )

    assert config.root == {
        "limit": 1.5,
        "enabled": True,
        "empty": None,
        "path": "data/input.json",
    }
    with pytest.raises(ValueError, match="must be a JSON scalar"):
        config_module.ParameterConfig.model_validate({"limit": {"value": 1}})
    with pytest.raises(ValueError, match="finite number"):
        config_module.ParameterConfig.model_validate({"limit": float("nan")})


def test_runtime_bindings_resolve_nested_parameter_references() -> None:
    spec_definition = _spec_for_plan(PLAN)
    spec_definition.functions["load"].args["source"].type = "array[string]"
    read_invocation = dataclasses.replace(
        PLAN.invocations[0], arguments={"source": ["$params.source"]}
    )
    bindings = _bindings(
        spec_definition=spec_definition,
        parameters={"source": "/override/input.parquet"},
    )

    assert bindings.resolve_args(read_invocation) == {"source": ["/override/input.parquet"]}


def test_runtime_bindings_reject_function_kind_mismatch() -> None:
    read_invocation = dataclasses.replace(PLAN.invocations[0], function_kind="write")
    bindings = _bindings()

    with pytest.raises(ValueError, match="does not match function load kind read"):
        bindings.resolve_args(read_invocation)
