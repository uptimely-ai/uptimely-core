"""Prepare illustrative processing tables without executing the spec."""

from __future__ import annotations

import dataclasses
import itertools

from uptimely import plan as plan_module
from uptimely import spec
from uptimely.spec import function_kinds as functions
from uptimely.spec.model import base as model_base

UNASSIGNED_DATASET_LABEL = "Unassigned"
DIMENSION_COLOR = "#93c5fd"
UNPRODUCED_COLOR = "#cbd5e1"
__all__ = ["DataLineageColumn", "DataLineageStep", "build_context"]


@dataclasses.dataclass(frozen=True)
class DataLineageColumn:
    """A declared column, its role, and its producing step."""

    name: str
    type: str
    role: str
    color: str
    producer: int | None
    label: str | None = None


@dataclasses.dataclass(frozen=True)
class DataLineageInput:
    """Source profile schema and shared dimension keys for a transfer."""

    dataset: str
    dataset_label: str
    keys: list[DataLineageColumn]
    columns: list[DataLineageColumn]
    join_dimensions: list[str]
    row_count: int


@dataclasses.dataclass(frozen=True)
class DataLineageStep:
    """One processing table in dependency order."""

    number: int
    invocation_id: str
    function: str
    function_label: str
    operator: str
    kind: functions.FunctionKind
    profile: str
    dataset: str | None
    grain: str
    color: str
    columns: list[DataLineageColumn]
    dependencies: list[int]
    input_tables: list[DataLineageInput] = dataclasses.field(default_factory=list)
    main_columns: list[DataLineageColumn] = dataclasses.field(default_factory=list)
    row_count: int = 3
    dataset_label: str = UNASSIGNED_DATASET_LABEL


@dataclasses.dataclass(frozen=True)
class _FeatureSource:
    """A feature declaration together with its owning profile."""

    profile: spec.Profile
    dataset: spec.Profile
    feature: spec.Feature


def _dimension_columns(
    profile: spec.Profile, dimensions: dict[str, spec.Dimension]
) -> list[DataLineageColumn]:
    """Resolve selected profile grain keys from canonical dimension declarations."""
    columns = []
    for reference in profile.grain:
        dimension = dimensions[reference.dimension]
        resolution = dimension.resolutions[reference.resolution]
        columns.append(
            DataLineageColumn(
                name=resolution.key,
                type=resolution.type,
                role="Dimension",
                color=DIMENSION_COLOR,
                producer=None,
                label=dimension.name or resolution.key,
            )
        )
    return columns


class _DataLineageBuilder:
    """Resolve display metadata once and accumulate schemas in execution order."""

    def __init__(self, definition: spec.Spec, plan: plan_module.ExecutionPlan) -> None:
        self.definition = definition
        self.ordered_stages = [
            sorted(stage, key=lambda invocation: invocation.id) for stage in plan.execution_stages
        ]
        invocations = plan.invocations
        self.numbers = {
            invocation.id: number
            for number, invocation in enumerate(
                itertools.chain.from_iterable(self.ordered_stages), start=1
            )
        }
        self.colors = {
            invocation_id: f"hsl({(150 + number * 137) % 360}, 70%, 75%)"
            for invocation_id, number in self.numbers.items()
        }
        self.producers = {
            feature: max(producers, key=lambda item: self.numbers[item.id])
            for feature, producers in plan.features.items()
            if feature not in definition.grain_key_ids
        }
        self.features: dict[str, _FeatureSource] = {}
        for feature_id, feature in definition.features.items():
            if feature_id in definition.grain_key_ids:
                continue
            owner = definition.feature_owners[feature_id][-1]
            self.features[feature_id] = _FeatureSource(
                profile=definition.profiles_by_key[owner],
                dataset=definition.profiles_by_key[owner],
                feature=feature,
            )
        self.compact_datasets = {
            invocation.dataset_id
            for invocation in invocations
            if functions.FUNCTION_KINDS[invocation.function_kind].dimension_change == "remove"
        }
        self.compact_datasets.update(
            self.features[name].dataset.id
            for invocation in invocations
            if functions.FUNCTION_KINDS[invocation.function_kind].dimension_change == "add"
            for name in invocation.input_features
            if name in self.features
        )
        self.accumulated: dict[str | None, dict[str, DataLineageColumn]] = {}

    def build(self) -> list[list[DataLineageStep]]:
        """Build stage cards in dependency order."""
        return [[self._step(invocation) for invocation in stage] for stage in self.ordered_stages]

    def _feature_column(self, name: str, role: str) -> DataLineageColumn:
        """Resolve a feature's label, type, and producer color."""
        source = self.features.get(name)
        key_dimension = None
        for _, profile in self.definition.profile_items:
            for reference in profile.grain:
                dimension = self.definition.dimensions[reference.dimension]
                resolution = dimension.resolutions[reference.resolution]
                if resolution.key == name:
                    key_dimension = (dimension, resolution)
                    break
            if key_dimension is not None:
                break
        declaration = source.feature if source is not None else None
        producer = self.producers.get(name)
        color = DIMENSION_COLOR if key_dimension is not None else UNPRODUCED_COLOR
        if producer is not None:
            color = self.colors[producer.id]
        key_type = key_dimension[1].type if key_dimension is not None else None
        label = (
            key_dimension[0].name or name
            if key_dimension is not None
            else declaration.name or name
            if declaration is not None
            else name
        )
        return DataLineageColumn(
            name=name,
            type=declaration.type or "Unspecified"
            if declaration is not None
            else key_type or "Unspecified",
            role=role,
            color=color,
            producer=self.numbers[producer.id] if producer is not None else None,
            label=label,
        )

    def _input_tables(
        self,
        invocation: plan_module.Invocation,
        profile: spec.Profile,
        columns: list[DataLineageColumn],
    ) -> list[DataLineageInput]:
        """Group cross-dataset inputs with their source dimensions."""
        if functions.FUNCTION_KINDS[invocation.function_kind].is_effect:
            return []
        source_columns: dict[str, list[DataLineageColumn]] = {}
        for column in columns:
            source = self.features.get(column.name)
            if (
                column.role == "Input"
                and source is not None
                and source.dataset.id != invocation.dataset_id
            ):
                source_columns.setdefault(source.dataset.id, []).append(column)

        tables = []
        profile_key = self.definition.profile_keys[profile.id]
        target_keys = set(self.definition.grain_keys_by_profile[profile_key])
        for source_id, inputs in source_columns.items():
            source = self.features[inputs[0].name]
            tables.append(
                DataLineageInput(
                    dataset=source_id,
                    dataset_label=source.dataset.name or source_id,
                    keys=_dimension_columns(source.profile, self.definition.dimensions),
                    columns=inputs,
                    join_dimensions=[
                        key
                        for key in self.definition.grain_keys_by_profile[
                            self.definition.profile_keys[source.profile.id]
                        ]
                        if key in target_keys
                    ],
                    row_count=1 if source_id in self.compact_datasets else 3,
                )
            )
        return tables

    def _main_columns(
        self, invocation: plan_module.Invocation, columns: list[DataLineageColumn]
    ) -> list[DataLineageColumn]:
        """Keep materialized columns, moving replaced outputs to the end."""
        previous = self.accumulated.setdefault(invocation.dataset_id, {})
        inputs = set(invocation.input_features)
        current = {
            name: dataclasses.replace(column, role="Input" if name in inputs else "Existing")
            for name, column in previous.items()
        }
        if not functions.FUNCTION_KINDS[invocation.function_kind].is_effect:
            for column in columns:
                if column.role == "Output":
                    current.pop(column.name, None)
                    current[column.name] = column
                    previous[column.name] = column
        return list(current.values())

    def _step(self, invocation: plan_module.Invocation) -> DataLineageStep:
        """Assemble one invocation's schema, input tables, and dependencies."""
        profile = self.definition.profiles[invocation.dataset_id]
        kind = functions.FUNCTION_KINDS[invocation.function_kind]
        dataset = (
            self.definition.profiles.get(invocation.dataset_id) if invocation.dataset_id else None
        )
        grain_keys = set(
            self.definition.grain_keys_by_profile[self.definition.profile_keys[profile.id]]
        )
        input_role = "Declared input" if kind.is_effect else "Input"
        columns = _dimension_columns(profile, self.definition.dimensions)
        columns.extend(
            self._feature_column(name, role)
            for role, names in (
                (input_role, invocation.input_features),
                ("Output", invocation.output_features),
            )
            for name in names
            if name not in grain_keys
        )
        function = self.definition.functions.get(invocation.function_id)
        dataset_label = UNASSIGNED_DATASET_LABEL
        if invocation.dataset_id:
            dataset_label = (
                dataset.name if dataset is not None and dataset.name else invocation.dataset_id
            )
        return DataLineageStep(
            number=self.numbers[invocation.id],
            invocation_id=invocation.id,
            function=invocation.function_id,
            function_label=function.name or invocation.function_id
            if function is not None
            else invocation.function_id,
            operator=model_base.humanize_identifier(invocation.operator_id),
            kind=kind,
            profile=profile.id,
            dataset=invocation.dataset_id,
            dataset_label=dataset_label,
            grain=", ".join(
                self.definition.grain_keys_by_profile[self.definition.profile_keys[profile.id]]
            ),
            color=self.colors[invocation.id],
            columns=columns,
            dependencies=sorted(
                self.numbers[dependency] for dependency in invocation.dependency_ids
            ),
            input_tables=self._input_tables(invocation, profile, columns),
            main_columns=self._main_columns(invocation, columns),
            row_count=1 if invocation.dataset_id in self.compact_datasets else 3,
        )


def _build_stages(
    spec_definition: spec.Spec, execution_plan: plan_module.ExecutionPlan
) -> list[list[DataLineageStep]]:
    """Build typed table schemas with colors inherited from feature producers."""
    return _DataLineageBuilder(spec_definition, execution_plan).build()


def build_context(
    spec_definition: spec.Spec,
    execution_plan: plan_module.ExecutionPlan,
) -> dict[str, object]:
    """Prepare data-lineage display data without writing files.

    Args:
        spec_definition: Spec document model.
        execution_plan: Compiled plan; no analytical functions are called.

    Returns:
        Declared processing tables grouped by dependency stage.
    """
    return {"stages": _build_stages(spec_definition, execution_plan)}
