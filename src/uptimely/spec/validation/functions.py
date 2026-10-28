"""Atomic function return and dataframe argument contract checks."""

from __future__ import annotations

from uptimely.spec import model as spec_model

from .. import functions
from . import context as context_module
from . import errors


def validate_return_kind(
    function_id: str,
    function: spec_model.FunctionTemplate,
    dataframe_inputs: int,
) -> context_module.ValidationResult:
    """Require the return kind defined by the function's kind."""
    kind = function.kind
    expected = functions.KIND_RETURN_KINDS[kind]
    if function.returns != expected:
        return errors.SpecError(
            f"Kind {kind} must declare returns={expected}."
            + functions.kind_hint(function.returns, dataframe_inputs),
            code="invalid_function_return_contract",
            path=("functions", function_id, "returns"),
        )
    return None


def validate_dataframe_count(
    function_id: str,
    function: spec_model.FunctionTemplate,
    dataframe_inputs: int,
) -> context_module.ValidationResult:
    """Require the dataframe argument count defined by the function kind."""
    kind = function.kind
    expected = functions.KIND_DATAFRAME_INPUT_COUNTS[kind]
    if expected is not None and dataframe_inputs != expected:
        return errors.SpecError(
            f"Kind {kind} requires {expected} dataframe "
            f"argument(s), got {dataframe_inputs}."
            + functions.kind_hint(function.returns, dataframe_inputs),
            code="invalid_function_input_contract",
            path=("functions", function_id, "args"),
        )
    return None
