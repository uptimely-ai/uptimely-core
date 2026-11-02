"""Atomic function return and dataframe argument contract checks."""

from __future__ import annotations

import logging

from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_return_kind(spec: spec_model.Spec) -> None:
    """Require the return kind defined by the function's kind."""
    logger.debug("    - checking function return contracts")
    for function_id, function, dataframe_inputs in spec.functions.iter_functions():
        kind = function.kind
        expected = functions.FUNCTION_KINDS[kind].returns
        if function.returns != expected:
            raise errors.SpecError(
                f"Kind {kind} must declare returns={expected}."
                + functions.kind_hint(function.returns, dataframe_inputs),
                code="invalid_function_return_contract",
                path=("functions", function_id, "returns"),
            )


def validate_dataframe_count(spec: spec_model.Spec) -> None:
    """Require the dataframe argument count defined by the function kind."""
    logger.debug("    - checking function dataframe argument counts")
    for function_id, function, dataframe_inputs in spec.functions.iter_functions():
        kind = function.kind
        expected = functions.FUNCTION_KINDS[kind].dataframe_inputs
        if expected is not None and dataframe_inputs != expected:
            raise errors.SpecError(
                f"Kind {kind} requires {expected} dataframe argument(s), got {dataframe_inputs}."
                + functions.kind_hint(function.returns, dataframe_inputs),
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            )
