"""Render processing tables and their dependencies without executing spec."""

from __future__ import annotations

import dataclasses

from uptimely import execution_plan, spec
from uptimely.explorer import render
from uptimely.spec import functions
from uptimely.spec.model import common as spec_common

SECTION = render.WebsiteSection(
    active_page="execution",
    pages=(
        render.WebsitePage(
            "execution/data_lineage.html.j2",
            render.WEBSITE_PAGES["execution"]["data_lineage"],
            active_section="data_lineage",
        ),
    ),
)
UNASSIGNED_DATASET_LABEL = "Unassigned"
DIMENSION_COLOR = "#93c5fd"
UNPRODUCED_COLOR = "#cbd5e1"
__all__ = ["SECTION", "DataLineageColumn", "DataLineageStep", "build_context"]


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
    """Source dataset schema and shared dimension keys for a transfer."""

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
    action: str
    kind: functions.FunctionKind
    entity: str
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
    """A feature declaration together with its owning table and entity."""

    entity: spec.Entity
    dataset: spec.Dataset
    feature: spec.Feature


def _dimension_columns(
    entity: spec.Entity, dimensions: dict[str, spec.Dimension]
) -> list[DataLineageColumn]:
    """Resolve entity dimensions from the canonical global declarations."""
    columns = []
    for name in entity.dimension_ids:
        dimension = dimensions[name]
        columns.append(
            DataLineageColumn(
                name=dimension.id,
                type=dimension.type,
                role="Dimension",
                color=DIMENSION_COLOR,
                producer=None,
                label=dimension.name or dimension.id,
            )
        )
    return columns


class _DataLineageBuilder:
    """Resolve display metadata once and accumulate schemas in execution order."""

    def __init__(self, definition: spec.Spec, plan: execution_plan.ExecutionPlan) -> None:
        self.definition = definition
        self.ordered_stages = [
            sorted(stage, key=lambda invocation: invocation.id) for stage in plan.execution_stages
        ]
        invocations = [invocation for stage in self.ordered_stages for invocation in stage]
        self.numbers = {
            invocation.id: number for number, invocation in enumerate(invocations, start=1)
        }
        self.colors = {
            invocation_id: f"hsl({(150 + number * 137) % 360}, 70%, 75%)"
            for invocation_id, number in self.numbers.items()
        }
        self.producers = {
            feature: invocation
            for invocation in invocations
            for feature in invocation.output_features
            if feature not in definition.dimensions
        }
        self.features = {
            feature.id: _FeatureSource(entity, dataset, feature)
            for entity in definition.entities.values()
            for dataset in entity.datasets.values()
            for feature in dataset.features.values()
            if feature.id not in definition.dimensions
        }
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
        dimension = self.definition.dimensions.get(name)
        declaration = source.feature if source is not None else dimension
        producer = self.producers.get(name)
        color = DIMENSION_COLOR if dimension is not None else UNPRODUCED_COLOR
        if producer is not None:
            color = self.colors[producer.id]
        return DataLineageColumn(
            name=name,
            type=declaration.type or "Unspecified" if declaration is not None else "Unspecified",
            role=role,
            color=color,
            producer=self.numbers[producer.id] if producer is not None else None,
            label=declaration.name or name if declaration is not None else name,
        )

    def _input_tables(
        self,
        invocation: execution_plan.Invocation,
        entity: spec.Entity,
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
        target_dimensions = set(entity.dimension_ids)
        for source_id, inputs in source_columns.items():
            source = self.features[inputs[0].name]
            tables.append(
                DataLineageInput(
                    dataset=source_id,
                    dataset_label=source.dataset.name or source_id,
                    keys=_dimension_columns(source.entity, self.definition.dimensions),
                    columns=inputs,
                    join_dimensions=[
                        dimension.id
                        for dimension in source.entity.dimensions
                        if dimension.id in target_dimensions
                    ],
                    row_count=1 if source_id in self.compact_datasets else 3,
                )
            )
        return tables

    def _main_columns(
        self, invocation: execution_plan.Invocation, columns: list[DataLineageColumn]
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

    def _step(self, invocation: execution_plan.Invocation) -> DataLineageStep:
        """Assemble one invocation's schema, input tables, and dependencies."""
        entity = self.definition.entities[invocation.entity_id]
        kind = functions.FUNCTION_KINDS[invocation.function_kind]
        dataset = entity.datasets.get(invocation.dataset_id)
        dimensions = set(entity.dimension_ids)
        input_role = "Declared input" if kind.is_effect else "Input"
        columns = _dimension_columns(entity, self.definition.dimensions)
        columns.extend(
            self._feature_column(name, role)
            for role, names in (
                (input_role, invocation.input_features),
                ("Output", invocation.output_features),
            )
            for name in names
            if name not in dimensions
        )
        function = self.definition.functions.get(invocation.function_id)
        dataset_label = UNASSIGNED_DATASET_LABEL
        if invocation.dataset_id:
            dataset_label = entity.datasets[invocation.dataset_id].name or invocation.dataset_id
        return DataLineageStep(
            number=self.numbers[invocation.id],
            invocation_id=invocation.id,
            function=invocation.function_id,
            function_label=function.name or invocation.function_id
            if function is not None
            else invocation.function_id,
            action=spec_common.humanize_identifier(invocation.mapping_id),
            kind=kind,
            entity=invocation.entity_id,
            dataset=invocation.dataset_id,
            dataset_label=dataset_label,
            grain=dataset.row_scope.grain if dataset is not None else "",
            color=self.colors[invocation.id],
            columns=columns,
            dependencies=sorted(
                self.numbers[dependency] for dependency in invocation.dependency_ids
            ),
            input_tables=self._input_tables(invocation, entity, columns),
            main_columns=self._main_columns(invocation, columns),
            row_count=1 if invocation.dataset_id in self.compact_datasets else 3,
        )


def _build_stages(
    spec_definition: spec.Spec, execution_plan: execution_plan.ExecutionPlan
) -> list[list[DataLineageStep]]:
    """Build typed table schemas with colors inherited from feature producers."""
    return _DataLineageBuilder(spec_definition, execution_plan).build()


def build_context(
    spec_definition: spec.Spec,
    execution_plan: execution_plan.ExecutionPlan,
) -> dict[str, object]:
    """Prepare data-lineage display data without rendering or writing pages.

    Args:
        spec_definition: Spec document model.
        execution_plan: Compiled plan; no analytical functions are called.

    Returns:
        Declared processing tables grouped by dependency stage.
    """
    return {"stages": _build_stages(spec_definition, execution_plan)}
