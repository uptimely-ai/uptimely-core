"""Atomic function return and dataframe argument contract checks."""

from __future__ import annotations

import collections.abc

from uptimely.spec import arg_types, functions
from uptimely.spec import model as spec_model

from . import errors


def iter_functions(
    model: spec_model.Spec,
) -> collections.abc.Iterator[tuple[str, spec_model.FunctionTemplate, int]]:
    """Yield each function and its dataframe-argument count."""
    return (
        (
            function_id,
            function,
            sum(argument.type == arg_types.DATAFRAME for argument in function.args.values()),
        )
        for function_id, function in model.functions.root.items()
    )


def validate_return_kind(spec: spec_model.Spec) -> None:
    """Require the return kind defined by the function's kind."""
    for function_id, function, dataframe_inputs in iter_functions(spec):
        kind = function.kind
        expected = functions.KIND_RETURN_KINDS[kind]
        if function.returns != expected:
            raise errors.SpecError(
                f"Kind {kind} must declare returns={expected}."
                + functions.kind_hint(function.returns, dataframe_inputs),
                code="invalid_function_return_contract",
                path=("functions", function_id, "returns"),
            )


def validate_dataframe_count(spec: spec_model.Spec) -> None:
    """Require the dataframe argument count defined by the function kind."""
    for function_id, function, dataframe_inputs in iter_functions(spec):
        kind = function.kind
        expected = functions.KIND_DATAFRAME_INPUT_COUNTS[kind]
        if expected is not None and dataframe_inputs != expected:
            raise errors.SpecError(
                f"Kind {kind} requires {expected} dataframe argument(s), got {dataframe_inputs}."
                + functions.kind_hint(function.returns, dataframe_inputs),
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            )
