"""Encode Spec bindings as portable plan invocations."""

from __future__ import annotations

from collections import abc

import pydantic

from uptimely import spec
from uptimely.spec import arg_types, selectors
from uptimely.spec.model import profile as profile_module

from . import models

JSON_VALUE = pydantic.TypeAdapter(pydantic.JsonValue)
BUILTIN_MERGE_ENTRYPOINT = "uptimely.library.merge.polars:merge_by_grain"


class ArgumentEncoder:
    """Encode resolved binding values using the plan's result references."""

    @classmethod
    def encode(
        cls,
        value: pydantic.JsonValue,
        argument_type: str | None,
        datasets: abc.Mapping[str, str],
        fragment: str,
    ) -> pydantic.JsonValue:
        """Resolve dataframe arguments against earlier named results.

        Args:
            value: Resolved Spec argument or nested JSON value.
            argument_type: Declared Spec type of the value.
            datasets: Latest dataset result name for each profile.
            fragment: Result name of the current operator's fragment.

        Returns:
            A JSON value containing plan references where needed.

        Raises:
            ValueError: A required profile dataframe is unavailable.
        """
        if value == f"{selectors.OPERATOR_PREFIX}{selectors.CURRENT_ID}.fragment":
            return fragment
        if arg_types.is_dataframe(argument_type or "") and isinstance(value, str):
            if value in datasets:
                return datasets[value]
            if argument_type == arg_types.OPTIONAL_DATAFRAME:
                return None
            raise ValueError(f"Profile dataframe is unavailable: {value}")
        if isinstance(value, list):
            item_type = arg_types.array_item_type(argument_type) if argument_type else None
            return [cls.encode(item, item_type, datasets, fragment) for item in value]
        if isinstance(value, dict):
            value_type = arg_types.object_value_type(argument_type) if argument_type else None
            return {
                key: cls.encode(item, value_type, datasets, fragment) for key, item in value.items()
            }
        return value


class InvocationEncoder:
    """Encode ordered invocations while tracking the latest profile results."""

    def __init__(self, spec_definition: spec.Spec) -> None:
        """Create an encoder for one ordered plan."""
        self.spec_definition = spec_definition
        self.datasets: dict[str, str] = {}

    def encode(
        self,
        invocation_id: str,
        semantics: models.InvocationSemantics,
        *,
        return_type: str | None = None,
    ) -> models.Invocation:
        """Encode one scheduled invocation.

        Args:
            invocation_id: Identifier assigned by the compiler.
            semantics: Invocation contract derived from the Spec.
            return_type: Inspected Python return annotation, if available.

        Returns:
            A portable invocation with encoded arguments and return name.

        Raises:
            ValueError: Required invocation metadata or a dataframe is unavailable.
        """
        profile = semantics.profile_id
        if profile is None:
            raise ValueError(f"Missing profile for invocation {invocation_id}")
        operator = self.spec_definition.profiles[profile].assembly[semantics.operator_id]
        function = self.spec_definition.functions[semantics.function_id]
        if not function.entrypoint:
            raise ValueError(f"Missing entrypoint for function {semantics.function_id}")
        outputs = [
            feature
            for feature in operator.output_features
            if feature not in semantics.target_identifiers
        ]
        feature_id = (
            outputs[0]
            if semantics.role == profile_module.OperatorBindingRole.COMPUTE and len(outputs) == 1
            else None
        )
        resolved = operator.resolve_args(
            function_id=semantics.function_id,
            profile_id=profile,
            identifiers_by_profile=self.spec_definition.identifiers_by_profile,
            resources=self.spec_definition.binding_resources,
            role=semantics.role,
            feature_id=feature_id,
        )
        fragment = models.Variable.encode(models.Variable.FRAGMENT, profile, semantics.operator_id)
        arguments = {
            name: ArgumentEncoder.encode(
                JSON_VALUE.validate_python(value, strict=True),
                function.args[name].type if name in function.args else None,
                self.datasets,
                fragment,
            )
            for name, value in resolved.items()
        }
        if (
            semantics.role == profile_module.OperatorBindingRole.MERGE
            and function.entrypoint == BUILTIN_MERGE_ENTRYPOINT
        ):
            arguments["key_columns"] = [
                key for key in semantics.fragment_keys if key not in semantics.target_identifiers
            ]
        if semantics.result == models.InvocationResultKind.NONE:
            result = None
        elif semantics.role == profile_module.OperatorBindingRole.MERGE:
            result = models.Variable.encode(models.Variable.MERGE, profile, semantics.operator_id)
        elif semantics.result == models.InvocationResultKind.FRAGMENT:
            result = fragment
        else:
            result = models.Variable.encode(models.Variable.DATASET, profile, semantics.operator_id)

        invocation = models.Invocation(
            id=invocation_id,
            entrypoint=function.entrypoint,
            arguments=arguments,
            returns=result,
            semantics=semantics.__replace__(return_type=return_type),
        )
        if semantics.result == models.InvocationResultKind.TARGET and result is not None:
            self.datasets[profile] = result
        return invocation
