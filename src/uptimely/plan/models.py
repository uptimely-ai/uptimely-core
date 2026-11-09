"""Portable execution-plan data transfer objects."""

from __future__ import annotations

import functools
import typing

import pydantic

from uptimely import spec
from uptimely.spec import operator_kinds as functions
from uptimely.spec import row_context as uptimely_row_context

PLAN_VERSION = 9
NonEmptyString = typing.Annotated[str, pydantic.Field(min_length=1)]


class _InvocationNode(typing.Protocol):
    """Compiler node fields needed to create its portable representation."""

    function_id: str
    profile_id: str
    operator_id: str
    role: typing.Literal["compute", "merge"]
    result: typing.Literal["none", "target", "fragment"]
    operator_kind: functions.OperatorKindId
    output_features: tuple[str, ...]
    input_features: tuple[str, ...]
    row_context: uptimely_row_context.RowContext | None

    @property
    def node_id(self) -> str: ...


class _PlanModel(pydantic.BaseModel):
    """Strict immutable base for portable plan metadata."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True, frozen=True)

    def __replace__(self, **changes: typing.Any) -> typing.Self:
        """Return a revalidated copy with selected fields replaced."""
        values = {name: getattr(self, name) for name in type(self).model_fields}
        return type(self).model_validate({**values, **changes})


class Package(_PlanModel):
    """Portable installed-package provenance for a module entrypoint."""

    distribution: str | None
    version: str | None


class Stage(pydantic.RootModel[list[NonEmptyString]]):
    """Portable group of invocation identifiers scheduled at the same time."""

    model_config = pydantic.ConfigDict(strict=True, frozen=True)

    @property
    def invocation_ids(self) -> list[str]:
        """Return the invocation identifiers assigned to this stage."""
        return self.root

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate through invocation identifiers in stage order."""
        return iter(self.root)


class Invocation(_PlanModel):
    """Portable representation of one compiler-created executable invocation."""

    id: NonEmptyString
    role: typing.Literal["compute", "merge"]
    result: typing.Literal["none", "target", "fragment"]
    operator_kind: functions.OperatorKindId
    entrypoint: NonEmptyString
    function_id: NonEmptyString
    operator_id: NonEmptyString
    profile_id: NonEmptyString | None
    arguments: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    dependency_ids: list[NonEmptyString] = pydantic.Field(default_factory=list)
    output_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    input_features: list[NonEmptyString] = pydantic.Field(default_factory=list)
    row_context: uptimely_row_context.RowContext | None = None
    id_columns: list[NonEmptyString] = pydantic.Field(default_factory=list)
    identifier_columns: list[NonEmptyString] = pydantic.Field(default_factory=list)
    column_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)
    argument_types: dict[NonEmptyString, NonEmptyString] = pydantic.Field(default_factory=dict)
    return_type: str | None = None
    package: Package | None = None

    @classmethod
    def from_node(
        cls,
        spec_definition: spec.Spec,
        node: _InvocationNode,
        *,
        dependency_ids: list[str],
        return_type: str | None,
        package: Package,
    ) -> typing.Self:
        """Create a portable invocation from a compiler node and resolved metadata.

        The compiler supplies dependency IDs, signature metadata, and package
        provenance. This factory resolves the node's Spec-backed arguments and
        copies its declared invocation data; it does not determine graph edges
        or execution order.

        Args:
            spec_definition: The validated source Spec.
            node: Compiler-created node to represent in the plan.
            dependency_ids: IDs of the node's direct prerequisites.
            return_type: Portable return annotation, if signature validation is enabled.
            package: Portable package provenance for the node's entrypoint.

        Returns:
            The portable invocation corresponding to the compiler node.

        Raises:
            ValueError: If the node's function does not declare an entrypoint.
        """
        function = spec_definition.functions.get(node.function_id)
        if function is None or not function.entrypoint:
            raise ValueError(
                f"Missing entrypoint for function {node.function_id} "
                f"used by operator {node.operator_id}"
            )
        profile_key = spec_definition.profile_keys[node.profile_id]
        id_columns = spec_definition.grain_keys_by_profile[profile_key]
        operator = spec_definition.profiles[node.profile_id].assembly[node.operator_id]
        arguments = operator.resolve_args(
            role=node.role,
            function_id=node.function_id,
            operator_kind=node.operator_kind,
            profile_id=node.profile_id,
            grain_keys_by_profile=spec_definition.grain_keys_by_profile,
            resources=spec_definition.binding_resources,
            id_columns=id_columns,
        )
        profile = spec_definition.profiles[node.profile_id]
        column_types = {
            feature_id: feature.type
            for feature_id, feature in profile.features.items()
            if feature.type is not None
        } | spec_definition.grain_key_types_by_profile[profile_key]
        identifier_types = spec_definition.identifier_types_by_profile[profile_key]
        column_types |= identifier_types
        return cls(
            id=node.node_id,
            role=node.role,
            result=node.result,
            operator_kind=node.operator_kind,
            entrypoint=function.entrypoint,
            function_id=node.function_id,
            operator_id=node.operator_id,
            profile_id=node.profile_id,
            output_features=list(node.output_features),
            input_features=list(node.input_features),
            arguments=arguments,
            dependency_ids=dependency_ids,
            row_context=node.row_context,
            id_columns=list(id_columns),
            identifier_columns=list(identifier_types),
            column_types=column_types,
            argument_types={key: argument.type for key, argument in function.args.items()},
            return_type=return_type,
            package=package,
        )

    @pydantic.field_validator("entrypoint", "function_id", "operator_id", mode="before")
    @classmethod
    def require_declared_identifier(cls, value: object, info: pydantic.ValidationInfo) -> object:
        """Keep declaration-specific errors clear for required invocation strings."""
        if not isinstance(value, str) or not value:
            field_name = {
                "entrypoint": "an entrypoint",
                "function_id": "a function_id",
                "operator_id": "an operator_id",
            }[info.field_name]
            raise ValueError(f"Invocations must declare {field_name}")
        return value

    @pydantic.model_validator(mode="after")
    def validate_output_features(self) -> typing.Self:
        """Require valid role/result combinations and distinct invocation outputs."""
        if len(set(self.output_features)) != len(self.output_features):
            raise ValueError("Invocation output_features must be unique")
        if len(set(self.identifier_columns)) != len(self.identifier_columns):
            raise ValueError("Invocation identifier_columns must be unique")
        if self.role == "merge" and self.result != "target":
            raise ValueError("Merge invocations must have result='target'")
        if self.result == "fragment" and self.role != "compute":
            raise ValueError("Only compute invocations may have result='fragment'")
        if (
            self.role == "compute"
            and self.operator_kind == functions.COLLAPSE
            and not self.output_features
        ):
            raise ValueError("Collapse must declare output_features")
        return self


class ExecutionPlan(_PlanModel):
    """Portable invocations and the compiler-selected execution schedule."""

    plan_version: typing.Literal[9]
    required_backend: NonEmptyString
    invocations: list[Invocation]
    stages: list[Stage]

    @pydantic.model_validator(mode="before")
    @classmethod
    def validate_supported_version(cls, value: object) -> object:
        """Reject incompatible plan versions before parsing the versioned schema."""
        if isinstance(value, dict) and "plan_version" in value:
            _validate_plan_version(value["plan_version"])
        return value

    @pydantic.model_validator(mode="after")
    def validate_plan_contracts(self) -> typing.Self:
        """Validate invocation consistency and the compiler-selected schedule."""
        invocations_by_id = {invocation.id: invocation for invocation in self.invocations}
        invocation_ids = {invocation.id for invocation in self.invocations}
        if len(invocation_ids) != len(self.invocations):
            raise ValueError("Plan contains duplicate invocation ids")
        self._validate_invocation_roles(invocations_by_id)
        self._validate_invocation_metadata()
        self._validate_execution_order(invocation_ids)
        return self

    def _validate_invocation_roles(self, invocations_by_id: dict[str, Invocation]) -> None:
        """Require every staged fragment to be consumed by one merge invocation."""
        merge_dependencies: dict[str, list[str]] = {}
        for invocation in self.invocations:
            if invocation.role != "merge":
                continue
            fragment_dependencies = [
                dependency_id
                for dependency_id in invocation.dependency_ids
                if dependency_id in invocations_by_id
                and invocations_by_id[dependency_id].role == "compute"
                and invocations_by_id[dependency_id].result == "fragment"
            ]
            if len(fragment_dependencies) != 1:
                raise ValueError(
                    f"Merge invocation {invocation.id} must depend on exactly one "
                    "fragment-producing compute invocation"
                )
            merge_dependencies.setdefault(fragment_dependencies[0], []).append(invocation.id)

        for invocation in self.invocations:
            if (
                invocation.result == "fragment"
                and len(merge_dependencies.get(invocation.id, [])) != 1
            ):
                raise ValueError(
                    f"Fragment invocation {invocation.id} must have exactly one merge consumer"
                )

    def _validate_invocation_metadata(self) -> None:
        """Require consistent entrypoints, return types, and packages."""
        entrypoint_and_return_by_function: dict[str, tuple[str, str | None]] = {}
        packages_by_entrypoint: dict[str, Package | None] = {}
        for invocation in self.invocations:
            metadata = (invocation.entrypoint, invocation.return_type)
            previous = entrypoint_and_return_by_function.setdefault(
                invocation.function_id, metadata
            )
            if previous[0] != invocation.entrypoint:
                raise ValueError(
                    f"Plan assigns function {invocation.function_id!r} to multiple entrypoints"
                )
            if previous[1] != invocation.return_type:
                raise ValueError(
                    f"Plan has conflicting return annotations for function "
                    f"{invocation.function_id!r}"
                )
            previous_package = packages_by_entrypoint.setdefault(
                invocation.entrypoint, invocation.package
            )
            if previous_package != invocation.package:
                raise ValueError(
                    f"Plan has conflicting package provenance for entrypoint "
                    f"{invocation.entrypoint!r}"
                )

    def _validate_execution_order(self, invocation_ids: set[str]) -> None:
        """Require a schedule that respects dependencies."""
        stage_by_invocation: dict[str, int] = {}
        for stage_number, stage in enumerate(self.stages):
            for invocation_id in stage.invocation_ids:
                stage_by_invocation[invocation_id] = stage_number

        dependencies = {
            dependency_id
            for invocation in self.invocations
            for dependency_id in invocation.dependency_ids
        }
        unknown = (dependencies | stage_by_invocation.keys()) - invocation_ids
        if unknown:
            raise ValueError("Plan references unknown invocation(s): " + ", ".join(sorted(unknown)))
        staged_count = sum(len(stage.invocation_ids) for stage in self.stages)
        if staged_count != len(stage_by_invocation) or stage_by_invocation.keys() != invocation_ids:
            raise ValueError("Plan must stage every invocation exactly once")
        for invocation in self.invocations:
            if any(
                stage_by_invocation[dependency_id] >= stage_by_invocation[invocation.id]
                for dependency_id in invocation.dependency_ids
            ):
                raise ValueError(
                    f"Dependencies for invocation {invocation.id} must be scheduled before it"
                )

    @functools.cached_property
    def invocations_by_id(self) -> dict[str, Invocation]:
        """Return the plan's invocation index keyed by opaque identifiers."""
        return {invocation.id: invocation for invocation in self.invocations}

    @functools.cached_property
    def execution_stages(self) -> list[list[Invocation]]:
        """Return staged invocations resolved from stage identifiers."""
        by_id = self.invocations_by_id
        return [
            [by_id[invocation_id] for invocation_id in stage.invocation_ids]
            for stage in self.stages
        ]

    @functools.cached_property
    def execution_invocations(self) -> list[Invocation]:
        """Return invocations in stage order, retaining the order within each stage."""
        return [invocation for stage in self.execution_stages for invocation in stage]

    @functools.cached_property
    def function_ids(self) -> set[str]:
        """Return the distinct functions used by this plan."""
        return {invocation.function_id for invocation in self.invocations}

    @functools.cached_property
    def profile_ids(self) -> set[str | None]:
        """Return the distinct profile IDs used by this plan."""
        return {invocation.profile_id for invocation in self.invocations}

    @functools.cached_property
    def arguments(self) -> dict[str, dict[str, typing.Any]]:
        """Return bound arguments keyed by invocation ID."""
        return {invocation.id: invocation.arguments for invocation in self.invocations}

    @functools.cached_property
    def features(self) -> dict[str, list[Invocation]]:
        """Return output feature IDs mapped to all their producing invocations."""
        features: dict[str, list[Invocation]] = {}
        for invocation in self.invocations:
            for feature in invocation.output_features:
                features.setdefault(feature, []).append(invocation)
        return features

    @functools.cached_property
    def invocations_by_kind(self) -> dict[functions.OperatorKindId, list[Invocation]]:
        """Return invocations grouped by derived operator label in declaration order."""
        grouped: dict[functions.OperatorKindId, list[Invocation]] = {}
        for invocation in self.invocations:
            grouped.setdefault(invocation.operator_kind, []).append(invocation)
        return grouped

    @functools.cached_property
    def calculated_features(self) -> set[str]:
        """Return distinct feature IDs produced by transformer invocations."""
        return {
            feature
            for kind, invocations in self.invocations_by_kind.items()
            if functions.OPERATOR_KINDS[kind].is_transformer
            for invocation in invocations
            for feature in invocation.output_features
        }

    @functools.cached_property
    def entrypoints(self) -> dict[str, None]:
        """Return distinct entrypoints in invocation declaration order."""
        return dict.fromkeys(invocation.entrypoint for invocation in self.invocations)

    @functools.cached_property
    def count_per_kind(self) -> dict[functions.OperatorKindId, int]:
        """Return invocation counts keyed by derived operator label, sorted by label."""
        return {
            kind: len(invocations) for kind, invocations in sorted(self.invocations_by_kind.items())
        }


def _validate_plan_version(version: object) -> None:
    """Reject plan versions this runtime cannot load."""
    if type(version) is not int or version != PLAN_VERSION:
        raise ValueError(
            f"Unsupported plan version: {version!r}. Supported version is {PLAN_VERSION}. "
            "Recompile the project build."
        )
