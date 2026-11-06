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
    for key, operator in spec.operator_items:
        function = spec.functions.root.get(operator.compute.function)
        if function is None:
            continue
        supplied = operator.arguments
        missing = function.args.keys() - supplied.keys()
        unknown = supplied.keys() - function.args.keys()
        if missing or unknown:
            details = (["missing arguments: " + ", ".join(sorted(missing))] if missing else []) + (
                ["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else []
            )
            raise errors.SpecError(
                f"Binding for function {operator.compute.function} has " + "; ".join(details),
                code="invalid_binding_arguments",
                path=(*spec.declaration_paths[key], "compute", "args"),
            )


def validate_selector_type(spec: spec_model.Spec) -> None:
    """Require a structural selector's argument type to match its value kind."""
    logger.debug("    - checking binding selector argument types")
    for path, value, argument_type in spec.binding_selectors_with_paths:
        if not isinstance(value, str) or not value.startswith(selectors.REFERENCE_PREFIX):
            continue
        if value.startswith(selectors.PROFILE_PREFIX) and value.endswith(
            selectors.DATAFRAME_SELECTOR
        ):
            expected = arg_types.DATAFRAME
        elif value.startswith(selectors.PROFILE_PREFIX) and value.endswith(
            selectors.PROFILE_GRAIN_IDS_SELECTOR
        ):
            expected = arg_types.array_of(arg_types.STRING)
        elif value.endswith(selectors.ID_SELECTOR) or any(
            value.startswith(prefix) and "." in value.removeprefix(prefix)
            for prefix in selectors.STRUCTURAL_PREFIXES
        ):
            expected = arg_types.STRING
        else:
            continue
        if argument_type != expected:
            raise errors.SpecError(
                f"Reference {value} requires argument type {expected}, got {argument_type}",
                code="invalid_binding_reference_type",
                path=path,
            )
    for key, operator in spec.operator_items:
        resolver = spec_model.BindingArgumentResolver(
            current_profile_id=key[0],
            feature_id=None,
            grain_keys_by_profile=spec.grain_keys_by_profile,
            resources=spec.binding_resources,
        )
        for value, path in operator.compute.values_with_paths:
            if not isinstance(value, str):
                continue
            prefix = next(
                (prefix for prefix in selectors.STRUCTURAL_PREFIXES if value.startswith(prefix)),
                None,
            )
            if prefix is None:
                continue
            _, _, attribute = value.removeprefix(prefix).partition(".")
            if not attribute or attribute in {"id", "dataframe", "grain.ids"}:
                continue
            try:
                resolver.resolve_arguments({"value": value})
            except ValueError as error:
                raise errors.SpecError(
                    str(error),
                    code="invalid_binding_selector",
                    path=(*spec.declaration_paths[key], "compute", "args", *path),
                ) from error
