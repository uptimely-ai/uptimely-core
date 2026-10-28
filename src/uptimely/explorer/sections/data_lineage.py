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
            render.WEBSITE_PAGES["execution"]["lineage"],
            active_section="lineage",
        ),
    ),
)
__all__ = ["SECTION", "DataLineageColumn", "DataLineageStep", "build_context"]


@dataclasses.dataclass(frozen=True)
class DataLineageColumn:
    """A declared column, its role, and its producing step."""

    name: str
    type: str
    role: str
    color: str
    producer: int | None
    external: bool = False


@dataclasses.dataclass(frozen=True)
class DataLineageStep:
    """One processing table in dependency order."""

    number: int
    invocation_id: str
    function: str
    function_kind: str
    entity: str
    dataset: str | None
    grain: str
    color: str
    columns: list[DataLineageColumn]
    dependencies: list[int]


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
                (
                    "Declared external output"
                    if invocation.function_kind == functions.ESCAPE
                    else "Output",
                    invocation.output_features,
                ),
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
                            producer is not None and producer.function_kind == functions.ESCAPE,
                        )
                    )
            dataset = entity.datasets.get(invocation.dataset_id)
            steps.append(
                DataLineageStep(
                    number=numbers[invocation.id],
                    invocation_id=invocation.id,
                    function=invocation.function_id,
                    function_kind=invocation.function_kind,
                    entity=invocation.entity_id,
                    dataset=invocation.dataset_id,
                    grain=dataset.row_scope.grain if dataset else "",
                    color=colors[invocation.id],
                    columns=columns,
                    dependencies=sorted(
                        numbers[dependency] for dependency in invocation.dependency_ids
                    ),
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
