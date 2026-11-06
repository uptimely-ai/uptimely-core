"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import logging

from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_arguments(spec: spec_model.Spec) -> None:
    """Require the supplied argument names to match the function signature."""
    logger.debug("    - checking binding argument names match function declarations")
    for key, operator in spec.operator_items:
        for name, binding in operator.bindings.items():
            function = spec.functions.root.get(binding.function)
            if function is None:
                continue
            missing, unknown = binding.argument_mismatches(function)
            if missing or unknown:
                details = (
                    ["missing arguments: " + ", ".join(sorted(missing))] if missing else []
                ) + (["unknown arguments: " + ", ".join(sorted(unknown))] if unknown else [])
                raise errors.SpecError(
                    f"Binding for function {binding.function} has " + "; ".join(details),
                    code="invalid_binding_arguments",
                    path=(*spec.declaration_paths[key], name, "args"),
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
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        target = operator.merge.args.get("target")
        if target is None or not target.is_current_dataset:
            raise errors.SpecError(
                "Merge target must reference the current profile dataframe",
                code="invalid_merge_binding",
                path=(*spec.declaration_paths[key], "merge", "args", "target"),
            )


def validate_merge_fragment(spec: spec_model.Spec) -> None:
    """Require merge bindings to use their operator's staged fragment."""
    logger.debug("    - checking merge bindings reference their staged fragment")
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        fragment = operator.merge.args.get("fragment")
        if fragment is None or not fragment.is_current_fragment:
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
        if operator.merge.feature_references:
            raise errors.SpecError(
                "Merge bindings cannot reference features; merge using dimension keys",
                code="invalid_merge_feature_reference",
                path=(*spec.declaration_paths[key], "merge", "args"),
            )


def validate_selector_type(spec: spec_model.Spec) -> None:
    """Require selector arguments to accept the selected value."""
    logger.debug("    - checking binding selector argument types")
    for path, argument, argument_type in spec.binding_arguments_with_paths:
        expected = argument.required_type(argument_type)
        if expected is None or argument_type == expected:
            continue

        raise errors.SpecError(
            f"Reference {argument.root} requires argument type {expected}, got {argument_type}",
            code="invalid_binding_reference_type",
            path=path,
        )


def validate_selector_metadata(spec: spec_model.Spec) -> None:
    """Require metadata selectors to resolve to declared resources and attributes."""
    logger.debug("    - checking binding selector metadata")
    for key, operator in spec.operator_items:
        profile_id, _ = key
        resolver = spec_model.BindingArgumentResolver(
            current_profile_id=profile_id,
            feature_id=None,
            grain_keys_by_profile=spec.grain_keys_by_profile,
            resources=spec.binding_resources,
        )
        for name, binding in operator.bindings.items():
            for argument, path in binding.metadata_references_with_paths:
                try:
                    argument.resolve(resolver)
                except ValueError as error:
                    raise errors.SpecError(
                        str(error),
                        code="invalid_binding_selector",
                        path=(*spec.declaration_paths[key], name, "args", *path),
                    ) from error
