"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import logging

from uptimely.spec import arg_types, functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_arguments(spec: spec_model.Spec) -> None:
    """Require the supplied argument names to match the function signature."""
    logger.debug("    - checking binding argument names match function declarations")
    for key, operator in spec.operator_items:
        for binding_name, binding in (("compute", operator.compute), ("merge", operator.merge)):
            if binding is None:
                continue
            function = spec.functions.root.get(binding.function)
            if function is None:
                continue
            supplied = binding.args
            missing = function.args.keys() - supplied.keys()
            unknown = supplied.keys() - function.args.keys()
            if missing or unknown:
                details = (
                    ["missing arguments: " + ", ".join(sorted(missing))] if missing else []
                ) + (["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else [])
                raise errors.SpecError(
                    f"Binding for function {binding.function} has " + "; ".join(details),
                    code="invalid_binding_arguments",
                    path=(*spec.declaration_paths[key], binding_name, "args"),
                )


def validate_merge_operator_kind(spec: spec_model.Spec) -> None:
    """Require merge bindings to belong to fragment-producing operators."""
    logger.debug("    - checking merge bindings belong to fragment-producing operators")
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        compute_function = spec.functions.root.get(operator.compute.function)
        if compute_function is not None:
            compute_kind = functions.FUNCTION_KINDS[compute_function.kind]
            if compute_function.kind == functions.VECTORIZE:
                raise errors.SpecError(
                    "Vectorize operators cannot declare a merge binding",
                    code="invalid_merge_binding",
                    path=(*spec.declaration_paths[key], "merge"),
                )
            if not compute_kind.produces_fragment:
                raise errors.SpecError(
                    f"{compute_function.kind.capitalize()} operators cannot declare a "
                    "merge binding",
                    code="invalid_merge_binding",
                    path=(*spec.declaration_paths[key], "merge"),
                )


def validate_merge_target(spec: spec_model.Spec) -> None:
    """Require merge bindings to use the current profile dataframe as their target."""
    logger.debug("    - checking merge bindings reference the current target")
    current_target = (
        f"{selectors.PROFILE_PREFIX}{selectors.CURRENT_ID}{selectors.DATAFRAME_SELECTOR}"
    )
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        target = operator.merge.args.get("target")
        if target is None or target.root != current_target:
            raise errors.SpecError(
                "Merge target must reference the current profile dataframe",
                code="invalid_merge_binding",
                path=(*spec.declaration_paths[key], "merge", "args", "target"),
            )


def validate_merge_fragment(spec: spec_model.Spec) -> None:
    """Require merge bindings to use their operator's staged fragment."""
    logger.debug("    - checking merge bindings reference their staged fragment")
    current_fragment = f"{selectors.OPERATOR_PREFIX}{selectors.CURRENT_ID}.fragment"
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        fragment = operator.merge.args.get("fragment")
        if fragment is None or fragment.root != current_fragment:
            raise errors.SpecError(
                "Merge fragment must reference this operator's staged fragment",
                code="invalid_merge_binding",
                path=(*spec.declaration_paths[key], "merge", "args", "fragment"),
            )


def validate_merge_feature_references(spec: spec_model.Spec) -> None:
    """Reject feature references in merge bindings."""
    logger.debug("    - checking merge bindings do not reference features")
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        if operator.merge.references_by_prefix[selectors.FEATURE_PREFIX]:
            raise errors.SpecError(
                "Merge bindings cannot reference features; merge using dimension keys",
                code="invalid_merge_feature_reference",
                path=(*spec.declaration_paths[key], "merge", "args"),
            )


def validate_selector_type(spec: spec_model.Spec) -> None:
    """Require selector arguments to accept the selected value."""
    logger.debug("    - checking binding selector argument types")
    for path, value, argument_type in spec.binding_selectors_with_paths:
        if not isinstance(value, str) or not value.startswith(selectors.REFERENCE_PREFIX):
            continue
        expected = _selector_value_type(value, argument_type)
        if expected is None or argument_type == expected:
            continue

        raise errors.SpecError(
            f"Reference {value} requires argument type {expected}, got {argument_type}",
            code="invalid_binding_reference_type",
            path=path,
        )


def _selector_value_type(value: str, argument_type: str) -> str | None:
    """Return the required argument type for a selector with a fixed value kind."""
    if value.startswith(selectors.OPERATOR_PREFIX):
        return arg_types.DATAFRAME
    if value.startswith(selectors.PROFILE_PREFIX):
        if value.endswith(selectors.DATAFRAME_SELECTOR):
            return (
                arg_types.OPTIONAL_DATAFRAME
                if argument_type == arg_types.OPTIONAL_DATAFRAME
                else arg_types.DATAFRAME
            )
        if value.endswith(selectors.PROFILE_GRAIN_IDS_SELECTOR):
            return arg_types.array_of(arg_types.STRING)
    if value.endswith(selectors.ID_SELECTOR) or any(
        value.startswith(prefix) and "." in value.removeprefix(prefix)
        for prefix in selectors.STRUCTURAL_PREFIXES
    ):
        return arg_types.STRING
    return None


def validate_selector_metadata(spec: spec_model.Spec) -> None:
    """Require metadata selectors to resolve to declared resources and attributes."""
    logger.debug("    - checking binding selector metadata")
    for key, operator in spec.operator_items:
        resolver = spec_model.BindingArgumentResolver(
            current_profile_id=key[0],
            feature_id=None,
            grain_keys_by_profile=spec.grain_keys_by_profile,
            resources=spec.binding_resources,
        )
        for binding_name, binding in (("compute", operator.compute), ("merge", operator.merge)):
            if binding is None:
                continue
            for argument, path in binding.references_with_paths:
                if not argument.is_metadata_reference:
                    continue
                try:
                    argument.resolve(resolver)
                except ValueError as error:
                    raise errors.SpecError(
                        str(error),
                        code="invalid_binding_selector",
                        path=(
                            *spec.declaration_paths[key],
                            binding_name,
                            "args",
                            *path,
                        ),
                    ) from error
