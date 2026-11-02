"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import logging

from uptimely.spec import arg_types, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_arguments(spec: spec_model.Spec) -> None:
    """Require the supplied argument names to match the function signature."""
    logger.debug("    - checking binding argument names match function declarations")
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None:
            continue
        supplied = action.arguments
        missing = function.args.keys() - supplied.keys()
        unknown = supplied.keys() - function.args.keys()
        if missing or unknown:
            details = (["missing arguments: " + ", ".join(sorted(missing))] if missing else []) + (
                ["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else []
            )
            raise errors.SpecError(
                f"Binding for function {action.binding.function} has " + "; ".join(details),
                code="invalid_binding_arguments",
                path=(*spec.declaration_paths[key], "binding", "args"),
            )


def validate_selector_type(spec: spec_model.Spec) -> None:
    """Require a structural selector's argument type to match its value kind."""
    logger.debug("    - checking binding selector argument types")
    for path, value, argument_type in spec.binding_selectors_with_paths:
        if not isinstance(value, str) or not value.startswith(selectors.REFERENCE_PREFIX):
            continue
        if value.startswith(selectors.DATASET_PREFIX) and value.endswith(
            selectors.DATAFRAME_SELECTOR
        ):
            expected = arg_types.DATAFRAME
        elif value.startswith(selectors.DATASET_PREFIX) and value.endswith(
            selectors.DIMENSION_IDS_SELECTOR
        ):
            expected = arg_types.array_of(arg_types.STRING)
        elif value.endswith(selectors.ID_SELECTOR):
            expected = arg_types.STRING
        else:
            continue
        if argument_type != expected:
            raise errors.SpecError(
                f"Reference {value} requires argument type {expected}, got {argument_type}",
                code="invalid_binding_reference_type",
                path=path,
            )
