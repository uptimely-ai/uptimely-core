import copy

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import plan as plan_module
from uptimely.engine import config as config_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import state as state_module

PLAN = plan_module.from_json("tests/fixtures/plans/simple_engine.json")


def _bindings(
    state: state_module.RuntimeState | None = None,
    parameters: dict[str, object] | None = None,
) -> bindings_module.RuntimeBindings:
    return bindings_module.RuntimeBindings(
        state or state_module.RuntimeState(),
        parameters or {},
    )


def test_runtime_bindings_resolve_nested_runtime_values_and_dataframe_ids() -> None:
    dataset = pl.DataFrame({"asset_id": ["A"]})
    fragment = pl.DataFrame({"reading": [2]})
    main = execution_support.dataset(dataset)
    main.fragments["reading"] = fragment_module.Fragment(fragment, ())
    state = state_module.RuntimeState(datasets={"telemetry": main})
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

    with pytest.raises(ValueError, match="Profile dataframe is unavailable: missing"):
        bindings.resolve_value("missing", "dataframe")


def test_runtime_bindings_resolve_staged_fragment_argument() -> None:
    staged = pl.DataFrame({"asset_id": ["A"], "reading": [2]})
    invocation = copy.replace(
        PLAN.invocations[0],
        arguments={"fragment": "$operators.@.fragment"},
        argument_types={"fragment": "dataframe"},
    )

    assert _bindings().resolve_args(invocation, staged_fragment=staged) == {"fragment": staged}


def test_runtime_bindings_reject_staged_fragment_without_merge_context() -> None:
    invocation = copy.replace(
        PLAN.invocations[0],
        arguments={"fragment": "$operators.@.fragment"},
        argument_types={"fragment": "dataframe"},
    )

    with pytest.raises(ValueError, match="Staged fragment is unavailable"):
        _bindings().resolve_args(invocation)


def test_runtime_bindings_reject_staged_fragment_with_incompatible_type() -> None:
    invocation = copy.replace(
        PLAN.invocations[0],
        arguments={"fragment": "$operators.@.fragment"},
        argument_types={"fragment": "string"},
    )

    with pytest.raises(ValueError, match="Merge fragment argument must have dataframe type"):
        _bindings().resolve_args(invocation, staged_fragment=pl.DataFrame())


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
    read_invocation = copy.replace(
        PLAN.invocations[0],
        arguments={"source": ["$params.source"]},
        argument_types={"source": "array[string]"},
    )
    bindings = _bindings(
        parameters={"source": "/override/input.parquet"},
    )

    assert bindings.resolve_args(read_invocation) == {"source": ["/override/input.parquet"]}


def test_runtime_bindings_use_invocation_types_independently_of_operator_kind() -> None:
    read_invocation = copy.replace(PLAN.invocations[0], operator_kind="write")
    bindings = _bindings()

    bindings = _bindings(parameters={"source": "input.json"})
    assert bindings.resolve_args(read_invocation) == {"source": "input.json"}
