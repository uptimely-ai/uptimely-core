"""Atomic argument-name and selector-type checks."""

from __future__ import annotations

import logging

from uptimely.spec import arg_types
from uptimely.spec import model as spec_model
from uptimely.spec.model import merge
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_default_merge_function(spec: spec_model.Spec) -> None:
    """Reject declarations that conflict with the builtin default merge function."""
    logger.debug("Check the builtin default merge declaration")
    if not any(
        operator.merge is not None and operator.merge.function == merge.DEFAULT_FUNCTION.id
        for operator in spec.operators
    ):
        return
    function = spec.functions.get(merge.DEFAULT_FUNCTION.id)
    if function is not None and function != merge.DEFAULT_FUNCTION:
        raise errors.SpecError(
            f"Function ID '{merge.DEFAULT_FUNCTION.id}' conflicts with the builtin merge "
            "declaration",
            code="function_id_conflict",
            path=("functions", merge.DEFAULT_FUNCTION.id),
        )


def validate_arguments(spec: spec_model.Spec) -> None:
    """Require the supplied argument names to match the function signature."""
    logger.debug("Check binding argument names match function declarations")
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


def validate_binding_contracts(spec: spec_model.Spec) -> None:
    """Validate arity and return contracts from binding positions, not callable kinds."""
    logger.debug("Check compute and merge binding contracts")
    for key, operator in spec.operator_items:
        for role, binding in operator.bindings.items():
            function = spec.functions.get(binding.function)
            if function is None:
                continue
            dataframe_count = sum(
                arg_types.is_dataframe(argument.type) for argument in function.args.values()
            )
            for value, path in binding.references_with_paths:
                if value.is_profile_dataframe_reference and len(path) != 1:
                    raise errors.SpecError(
                        f"Operator {key[1]} {role} has a nested dataframe reference; "
                        "bind dataframes as top-level arguments",
                        code="invalid_binding_arity",
                        path=(*spec.declaration_paths[key], role, "args", *path),
                    )
            if (role == "compute" and dataframe_count > 1) or (
                role == "merge" and dataframe_count != 2
            ):
                raise errors.SpecError(
                    f"Operator {key[1]} {role} binding has invalid dataframe arity: "
                    f"{dataframe_count}; expected {'zero or one' if role == 'compute' else 'two'}",
                    code="invalid_binding_arity",
                    path=(*spec.declaration_paths[key], role, "args"),
                )
            if (role == "merge" or operator.merge is not None) and function.returns != "dataframe":
                raise errors.SpecError(
                    f"Operator {key[1]} {role} binding must return a dataframe when merging",
                    code="invalid_merge_binding",
                    path=(*spec.declaration_paths[key], role, "function"),
                )
            for name, argument in function.args.items():
                if (
                    role == "merge"
                    and name in {"target", "fragment"}
                    and (
                        not arg_types.is_dataframe(argument.type)
                        or (name == "fragment" and argument.type != arg_types.DATAFRAME)
                    )
                ):
                    raise errors.SpecError(
                        f"Merge {name} must declare a dataframe argument",
                        code="invalid_merge_binding",
                        path=(*spec.declaration_paths[key], role, "args", name),
                    )
                if not arg_types.is_dataframe(argument.type) and "dataframe" in argument.type:
                    raise errors.SpecError(
                        "Nested dataframe arguments are unsupported; bind a top-level dataframe",
                        code="invalid_binding_arity",
                        path=(*spec.declaration_paths[key], role, "args", name),
                    )


def validate_merge_target(spec: spec_model.Spec) -> None:
    """Require merge bindings to use the current profile dataframe as their target."""
    logger.debug("Check merge bindings reference the current target")
    for key, operator in spec.operator_items:
        if operator.merge is None:
            continue
        target = operator.merge.args.get("target")
        if target is None or not target.is_current_profile_dataframe:
            raise errors.SpecError(
                "Merge target must reference the current profile dataframe",
                code="invalid_merge_binding",
                path=(*spec.declaration_paths[key], "merge", "args", "target"),
            )


def validate_merge_fragment(spec: spec_model.Spec) -> None:
    """Require merge bindings to use their operator's staged fragment."""
    logger.debug("Check merge bindings reference their staged fragment")
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
    logger.debug("Check merge bindings do not reference features")
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
    logger.debug("Check binding selector argument types")
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
    logger.debug("Check binding selector metadata")
    for key, operator in spec.operator_items:
        profile_id, _ = key
        for name, binding in operator.bindings.items():
            for argument, path in binding.metadata_references_with_paths:
                try:
                    argument.resolve(
                        profile_id,
                        grain_keys_by_profile=spec.grain_keys_by_profile,
                        resources=spec.binding_resources,
                        row_context=operator.row_context,
                    )
                except ValueError as error:
                    raise errors.SpecError(
                        str(error),
                        code="invalid_binding_selector",
                        path=(*spec.declaration_paths[key], name, "args", *path),
                    ) from error
