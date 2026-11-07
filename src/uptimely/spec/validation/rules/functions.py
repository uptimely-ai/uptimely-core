"""Atomic function return and dataframe argument contract checks."""

from __future__ import annotations

import logging

from uptimely.spec import arg_types
from uptimely.spec import function_kinds as functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_return_kind(spec: spec_model.Spec) -> None:
    """Require the return kind defined by the function's kind."""
    logger.debug("    - checking function return contracts")
    for function_id, function in spec.functions.root.items():
        try:
            function.check_return_contract()
        except ValueError as error:
            raise errors.SpecError(
                str(error),
                code="invalid_function_return_contract",
                path=("functions", function_id, "returns"),
            ) from error


def validate_dataframe_count(spec: spec_model.Spec) -> None:
    """Require the dataframe argument count defined by the function kind."""
    logger.debug("    - checking function dataframe argument counts")
    for function_id, function in spec.functions.root.items():
        try:
            function.check_dataframe_input_contract()
        except ValueError as error:
            raise errors.SpecError(
                str(error),
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            ) from error


def validate_nullable_dataframe_arguments(spec: spec_model.Spec) -> None:
    """Reserve nullable dataframe arguments for merge functions."""
    logger.debug("    - checking nullable dataframe arguments are reserved for merge functions")
    for function_id, function in spec.functions.root.items():
        if function.kind == functions.MERGE:
            continue
        if any(
            argument.type == arg_types.OPTIONAL_DATAFRAME for argument in function.args.values()
        ):
            raise errors.SpecError(
                "Nullable dataframe arguments are reserved for merge functions",
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            )


def validate_merge_target_argument(spec: spec_model.Spec) -> None:
    """Require merge functions to declare a nullable dataframe target."""
    logger.debug("    - checking merge function target arguments")
    for function_id, function in spec.functions.root.items():
        if function.kind != functions.MERGE:
            continue
        target = function.args.get("target")
        if target is None or target.type != arg_types.OPTIONAL_DATAFRAME:
            raise errors.SpecError(
                "Merge functions must declare target as 'dataframe | null'",
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            )


def validate_merge_fragment_argument(spec: spec_model.Spec) -> None:
    """Require merge functions to declare a dataframe fragment."""
    logger.debug("    - checking merge function fragment arguments")
    for function_id, function in spec.functions.root.items():
        if function.kind != functions.MERGE:
            continue
        fragment = function.args.get("fragment")
        if fragment is None or fragment.type != arg_types.DATAFRAME:
            raise errors.SpecError(
                "Merge functions must declare fragment as 'dataframe'",
                code="invalid_function_input_contract",
                path=("functions", function_id, "args"),
            )
