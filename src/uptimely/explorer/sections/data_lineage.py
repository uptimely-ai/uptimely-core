"""Render processing tables and their dependencies without executing spec."""

from __future__ import annotations

import dataclasses

from uptimely import execution_plan, spec
from uptimely.explorer import render
from uptimely.spec import functions

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
__all__ = ["SECTION", "DataLineageColumn", "DataLineageStep", "build_context"]


@dataclasses.dataclass(frozen=True)
class DataLineageColumn:
    """A declared column, its role, and its producing step."""

    name: str
    type: str
    role: str
    color: str
    producer: int | None


@dataclasses.dataclass(frozen=True)
class DataLineageInput:
    """Source dataset schema and shared dimension keys for a transfer."""

    dataset: str
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
    action: str
    function_kind: functions.FunctionKindId
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


def _humanize(identifier: str) -> str:
    """Return a title-cased label for a snake- or kebab-case identifier.

    Args:
        identifier: Spec identifier such as ``pump_telemetry_dataset``.

    Returns:
        Readable label such as ``Pump Telemetry Dataset``.
    """
    return identifier.replace("_", " ").replace("-", " ").title()


def _build_stages(
    spec_definition: spec.Spec, execution_plan: execution_plan.ExecutionPlan
) -> list[list[DataLineageStep]]:
    """Build typed table schemas with colors inherited from feature producers.

    Args:
        spec_definition: Declared dimensions, datasets, and column metadata.
        execution_plan: Compiled invocations and their dependencies.

    Returns:
        Processing tables grouped by dependency stage.
    """
    ordered_stages = [
        sorted(stage, key=lambda invocation: invocation.id)
        for stage in execution_plan.execution_stages
    ]
    invocations = [invocation for stage in ordered_stages for invocation in stage]
    numbers = {invocation.id: number for number, invocation in enumerate(invocations, 1)}
    colors = {
        invocation.id: f"hsl({(150 + number * 137) % 360}, 70%, 75%)"
        for number, invocation in enumerate(invocations, 1)
    }
    producers = {
        feature: invocation
        for invocation in invocations
        for feature in invocation.output_features
        if feature not in spec_definition.dimensions
    }
    feature_owners = {
        name: (entity, dataset)
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
        for name in dataset.features
        if name not in spec_definition.dimensions
    }
    feature_types = {
        name: feature.type or "Unspecified"
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
        for name, feature in dataset.features.items()
        if name not in spec_definition.dimensions
    }
    feature_types.update(
        {name: dimension.type for name, dimension in spec_definition.dimensions.items()}
    )
    compact_datasets = {
        invocation.dataset_id
        for invocation in invocations
        if invocation.function_kind == functions.COLLAPSE
    } | {
        feature_owners[name][1].id
        for invocation in invocations
        if invocation.function_kind == functions.EXPAND
        for name in invocation.input_features
        if name in feature_owners
    }
    accumulated: dict[str | None, dict[str, DataLineageColumn]] = {}
    stages: list[list[DataLineageStep]] = []
    for stage in ordered_stages:
        steps: list[DataLineageStep] = []
        for invocation in stage:
            entity = spec_definition.entities[invocation.entity_id]
            dimensions = entity.dimension_ids
            columns = [
                DataLineageColumn(
                    name, spec_definition.dimensions[name].type, "Dimension", "#93c5fd", None
                )
                for name in dimensions
            ]
            for role, features in (
                (
                    "Declared input" if invocation.function_kind == functions.ESCAPE else "Input",
                    invocation.input_features,
                ),
                ("Output", invocation.output_features),
            ):
                for feature in features:
                    if feature in dimensions:
                        continue
                    producer = producers.get(feature)
                    columns.append(
                        DataLineageColumn(
                            feature,
                            feature_types.get(feature, "Unspecified"),
                            role,
                            colors[producer.id]
                            if producer
                            else "#93c5fd"
                            if feature in spec_definition.dimensions
                            else "#cbd5e1",
                            numbers[producer.id] if producer else None,
                        )
                    )
            dataset = entity.datasets.get(invocation.dataset_id)
            input_tables: list[DataLineageInput] = []
            if invocation.function_kind != functions.ESCAPE:
                source_columns: dict[str, list[DataLineageColumn]] = {}
                for column in columns:
                    if column.role == "Input" and column.name in feature_owners:
                        _, source = feature_owners[column.name]
                        if source.id != invocation.dataset_id:
                            source_columns.setdefault(source.id, []).append(column)
                for source_id, inputs in source_columns.items():
                    source_entity, _ = feature_owners[inputs[0].name]
                    input_tables.append(
                        DataLineageInput(
                            dataset=source_id,
                            keys=[
                                DataLineageColumn(
                                    name,
                                    spec_definition.dimensions[name].type,
                                    "Dimension",
                                    "#93c5fd",
                                    None,
                                )
                                for name in source_entity.dimension_ids
                            ],
                            columns=inputs,
                            join_dimensions=[
                                name for name in source_entity.dimension_ids if name in dimensions
                            ],
                            row_count=1 if source_id in compact_datasets else 3,
                        )
                    )
            previous_columns = accumulated.setdefault(invocation.dataset_id, {})
            main_columns = [
                dataclasses.replace(
                    column,
                    role="Input" if name in invocation.input_features else "Existing",
                )
                for name, column in previous_columns.items()
            ]
            if invocation.function_kind != functions.ESCAPE:
                for column in columns:
                    if column.role == "Output":
                        main_columns = [
                            existing for existing in main_columns if existing.name != column.name
                        ]
                        main_columns.append(column)
                        previous_columns[column.name] = column
            steps.append(
                DataLineageStep(
                    number=numbers[invocation.id],
                    invocation_id=invocation.id,
                    function=invocation.function_id,
                    action=_humanize(invocation.mapping_id),
                    function_kind=invocation.function_kind,
                    entity=invocation.entity_id,
                    dataset=invocation.dataset_id,
                    dataset_label=(
                        _humanize(invocation.dataset_id)
                        if invocation.dataset_id
                        else UNASSIGNED_DATASET_LABEL
                    ),
                    grain=dataset.row_scope.grain if dataset else "",
                    color=colors[invocation.id],
                    columns=columns,
                    dependencies=sorted(
                        numbers[dependency] for dependency in invocation.dependency_ids
                    ),
                    input_tables=input_tables,
                    main_columns=main_columns,
                    row_count=1 if invocation.dataset_id in compact_datasets else 3,
                )
            )
        stages.append(steps)
    return stages


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
