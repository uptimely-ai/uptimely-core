"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely.spec import arg_types, selectors
from uptimely.spec import row_context as row_context_module
from uptimely.spec.model import profile as profile_module

PLAN_VERSION: typing.Final = 18
NonEmptyString = typing.Annotated[str, pydantic.Field(min_length=1)]


class Variable:
    """Encode and recognize named results in a plan."""

    DATASET = "$datasets."
    FRAGMENT = "$fragments."
    MERGE = "$dataset."
    PREFIXES = (DATASET, FRAGMENT, MERGE)

    @classmethod
    def encode(cls, prefix: str, profile: str, operator: str) -> str:
        """Return a qualified result name for one profile and operator."""
        if prefix not in cls.PREFIXES or not profile or not operator:
            raise ValueError("A result requires a valid prefix, profile, and operator")
        return f"{prefix}{profile}.{operator}"

    @classmethod
    def validate(cls, value: str) -> str:
        """Require a result name with a profile and operator."""
        for prefix in cls.PREFIXES:
            if value.startswith(prefix):
                profile, separator, operator = value.removeprefix(prefix).partition(".")
                if profile and separator and operator:
                    return value
                break
        raise ValueError(f"Malformed result reference: {value}")


class InvocationResultKind:
    """Analytical classification of an invocation's result."""

    Value = typing.Literal["none", "target", "fragment"]
    NONE: typing.Final = "none"
    TARGET: typing.Final = "target"
    FRAGMENT: typing.Final = "fragment"


class _PlanModel(pydantic.BaseModel):
    """Strict immutable base for portable plan metadata."""

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )

    def __replace__(self, **changes: typing.Any) -> typing.Self:
        """Return a revalidated copy with selected fields replaced."""
        values = {name: getattr(self, name) for name in type(self).model_fields}
        return type(self).model_validate({**values, **changes})


class Stage(pydantic.RootModel[list[NonEmptyString]]):
    """Ordered group of invocation identifiers in a plan schedule."""

    model_config = pydantic.ConfigDict(strict=True, frozen=True)

    @property
    def invocation_ids(self) -> list[str]:
        """Return the invocation identifiers assigned to this stage."""
        return self.root

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate through invocation identifiers in stage order."""
        return iter(self.root)


class InvocationSemantics(_PlanModel):
    """Analytical contract and Spec provenance for one function invocation."""

    role: profile_module.OperatorBindingRole.Value
    result: InvocationResultKind.Value
    produces_features: bool = False
    is_sink: bool = False
    is_workflow: bool = False
    is_seed: bool = False
    dataframe_input_scope: profile_module.DataFrameInputScope.Value = (
        profile_module.DataFrameInputScope.UNRESTRICTED
    )
    fragment_dimensions: profile_module.FragmentDimensions.Value = (
        profile_module.FragmentDimensions.NOT_APPLICABLE
    )
    row_count_relation: profile_module.RowCountRelation.Value = (
        profile_module.RowCountRelation.UNRESTRICTED
    )
    key_relation: profile_module.KeyRelation.Value = profile_module.KeyRelation.UNRESTRICTED
    row_order_relation: profile_module.RowOrderRelation.Value = (
        profile_module.RowOrderRelation.UNRESTRICTED
    )
    existing_data_relation: profile_module.ExistingDataRelation.Value = (
        profile_module.ExistingDataRelation.UNRESTRICTED
    )
    function_id: NonEmptyString
    operator_id: NonEmptyString
    profile_id: NonEmptyString | None
    output_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    input_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    row_context: row_context_module.RowContext | None = None
    target_identifiers: list[NonEmptyString] = pydantic.Field(default_factory=list)
    fragment_keys: list[NonEmptyString] = pydantic.Field(default_factory=list)
    output_types: dict[NonEmptyString, NonEmptyString | None] = pydantic.Field(default_factory=dict)
    column_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)
    argument_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)
    return_type: str | None = None

    @pydantic.field_validator("function_id", "operator_id", mode="before")
    @classmethod
    def require_declared_identifier(cls, value: object, info: pydantic.ValidationInfo) -> object:
        """Keep declaration-specific errors clear for required invocation strings."""
        if not isinstance(value, str) or not value:
            field_name = {"function_id": "a function_id", "operator_id": "an operator_id"}[
                info.field_name
            ]
            raise ValueError(f"Invocations must declare {field_name}")
        return value

    @pydantic.model_validator(mode="after")
    def validate_contracts(self) -> typing.Self:
        """Require valid role/result combinations and distinct invocation outputs."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Invocation output_features must be unique")
        if len(set(self.fragment_keys)) != len(self.fragment_keys):
            raise ValueError("Invocation fragment_keys must be unique")
        if (
            self.role == profile_module.OperatorBindingRole.MERGE
            and self.result != InvocationResultKind.TARGET
        ):
            raise ValueError("Merge invocations must have result='target'")
        if (
            self.result == InvocationResultKind.FRAGMENT
            and self.role != profile_module.OperatorBindingRole.COMPUTE
        ):
            raise ValueError("Only compute invocations may have result='fragment'")
        if (
            self.result == InvocationResultKind.FRAGMENT
            and self.fragment_dimensions == profile_module.FragmentDimensions.NOT_APPLICABLE
        ):
            raise ValueError("Fragment invocations must declare fragment dimensions")
        if self.is_workflow and (
            self.role != profile_module.OperatorBindingRole.COMPUTE
            or self.result != InvocationResultKind.NONE
            or not self.is_sink
            or any(arg_types.is_dataframe(value) for value in self.argument_types.values())
        ):
            raise ValueError("Workflow invocations must be non-dataframe sinks")
        return self


def _validate_dataframe_reference(value: str) -> str:
    """Require a qualified result reference."""
    return Variable.validate(value)


type DataframeReference = typing.Annotated[
    str, pydantic.AfterValidator(_validate_dataframe_reference)
]


class Invocation(_PlanModel):
    """A function call and an optional immutable return name."""

    id: NonEmptyString
    entrypoint: NonEmptyString
    arguments: dict[str, pydantic.JsonValue]
    returns: DataframeReference | None
    semantics: InvocationSemantics | None = None

    @functools.cached_property
    def referenced_results(self) -> tuple[str, ...]:
        """Return distinct result references in the invocation's arguments."""
        return tuple(
            dict.fromkeys(
                name for value in self.arguments.values() for name in _return_references(value)
            )
        )


class ExecutionPlan(_PlanModel):
    """A call schedule with named results and final dataset aliases."""

    plan_version: typing.Literal[18]
    required_backend: NonEmptyString
    invocations: list[Invocation]
    stages: list[Stage]
    datasets: dict[NonEmptyString, DataframeReference]

    @pydantic.field_validator("plan_version", mode="before")
    @classmethod
    def validate_version(cls, value: object) -> object:
        """Require the exact integer format version."""
        if type(value) is not int or value != PLAN_VERSION:
            raise ValueError(f"Unsupported plan version: {value!r}. Expected {PLAN_VERSION}.")
        return value

    @pydantic.model_validator(mode="after")
    def validate_schedule(self) -> typing.Self:
        """Check identifiers, single-assignment returns, and reference ordering."""
        invocations = {invocation.id: invocation for invocation in self.invocations}
        if len(invocations) != len(self.invocations):
            raise ValueError("Plan contains duplicate invocation IDs")

        order: dict[str, int] = {}
        for stage in self.stages:
            for invocation_id in stage:
                if invocation_id not in invocations:
                    raise ValueError(f"Stage references unknown invocation: {invocation_id}")
                if invocation_id in order:
                    raise ValueError(f"Invocation is staged more than once: {invocation_id}")
                order[invocation_id] = len(order)
        if order.keys() != invocations.keys():
            raise ValueError("Plan must stage every invocation exactly once")

        returns: dict[str, str] = {}
        for invocation in self.invocations:
            if invocation.returns is not None:
                if invocation.returns in returns:
                    raise ValueError(
                        f"Return name is assigned more than once: {invocation.returns}"
                    )
                returns[invocation.returns] = invocation.id

        for invocation in self.invocations:
            for argument in invocation.arguments.values():
                for name in _return_references(argument):
                    if name not in returns:
                        raise ValueError(f"Unknown return reference in {invocation.id}: {name}")
                    if order[returns[name]] >= order[invocation.id]:
                        raise ValueError(f"Return {name} must be produced before {invocation.id}")

        for dataset, name in self.datasets.items():
            if name not in returns:
                raise ValueError(f"Dataset {dataset} references unknown return: {name}")
        return self

    @functools.cached_property
    def invocations_by_id(self) -> dict[str, Invocation]:
        """Return invocations indexed by ID."""
        return {invocation.id: invocation for invocation in self.invocations}

    @functools.cached_property
    def execution_stages(self) -> list[list[Invocation]]:
        """Return invocations grouped in stage order."""
        return [
            [self.invocations_by_id[invocation_id] for invocation_id in stage]
            for stage in self.stages
        ]

    @functools.cached_property
    def execution_invocations(self) -> list[Invocation]:
        """Return invocations in stage order."""
        return [invocation for stage in self.execution_stages for invocation in stage]

    @functools.cached_property
    def entrypoints(self) -> dict[str, None]:
        """Return distinct entrypoints in invocation declaration order."""
        return dict.fromkeys(invocation.entrypoint for invocation in self.invocations)

    @functools.cached_property
    def input_invocations(self) -> dict[str, list[str]]:
        """Index producers explicitly referenced by each invocation's arguments."""
        producers = {
            invocation.returns: invocation.id
            for invocation in self.invocations
            if invocation.returns is not None
        }
        return {
            invocation.id: list(
                dict.fromkeys(producers[name] for name in invocation.referenced_results)
            )
            for invocation in self.invocations
        }

    @functools.cached_property
    def function_ids(self) -> set[str]:
        """Return declared function IDs from invocations with semantics."""
        return {
            invocation.semantics.function_id
            for invocation in self.invocations
            if invocation.semantics is not None
        }

    @functools.cached_property
    def profile_ids(self) -> set[str | None]:
        """Return declared profile IDs from invocations with semantics."""
        return {
            invocation.semantics.profile_id
            for invocation in self.invocations
            if invocation.semantics is not None
        }

    @functools.cached_property
    def features(self) -> dict[str, list[Invocation]]:
        """Index declared output features by their producing invocations."""
        features: dict[str, list[Invocation]] = {}
        for invocation in self.invocations:
            if invocation.semantics is not None:
                for feature in invocation.semantics.output_features:
                    features.setdefault(feature, []).append(invocation)
        return features

    @functools.cached_property
    def calculated_features(self) -> set[str]:
        """Return feature IDs from compute calls publishing targets."""
        return {
            feature
            for invocation in self.invocations
            if invocation.semantics is not None
            and invocation.semantics.role == profile_module.OperatorBindingRole.COMPUTE
            and invocation.semantics.result == InvocationResultKind.TARGET
            for feature in invocation.semantics.output_features
        }

    @functools.cached_property
    def count_per_role(self) -> dict[profile_module.OperatorBindingRole.Value, int]:
        """Count invocations by declared role."""
        counts: dict[profile_module.OperatorBindingRole.Value, int] = {}
        for invocation in self.invocations:
            if invocation.semantics is not None:
                role = invocation.semantics.role
                counts[role] = counts.get(role, 0) + 1
        return dict(sorted(counts.items()))


def _return_references(argument: pydantic.JsonValue) -> typing.Iterator[str]:
    """Yield named returns and validate runtime references in a JSON value."""
    if isinstance(argument, str):
        for prefix in Variable.PREFIXES:
            if argument == prefix[:-1] or argument.startswith(prefix):
                yield Variable.validate(argument)
                break
        for prefix in (selectors.PARAMS_PREFIX, selectors.PATHS_PREFIX):
            if argument == prefix[:-1] or (
                argument.startswith(prefix) and not argument.removeprefix(prefix).isidentifier()
            ):
                raise ValueError(f"Malformed runtime reference: {argument}")
    elif isinstance(argument, list):
        for item in argument:
            yield from _return_references(item)
    elif isinstance(argument, dict):
        for item in argument.values():
            yield from _return_references(item)
