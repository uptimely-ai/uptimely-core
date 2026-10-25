"""Render processing tables and their dependencies without executing spec."""

from __future__ import annotations

import dataclasses
import pathlib

from uptimely import execution_plan, project, spec
from uptimely.spec import operations

from . import render


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
    callable_id: str
    function: str
    operation: str
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
        execution_plan: Compiled callables and their dependencies.

    Returns:
        Processing tables grouped by dependency stage.
    """
    ordered_stages = [
        sorted(stage, key=lambda callable: callable.id) for stage in execution_plan.execution_stages
    ]
    callables = [callable for stage in ordered_stages for callable in stage]
    numbers = {callable.id: number for number, callable in enumerate(callables, 1)}
    colors = {
        callable.id: f"hsl({(150 + number * 137) % 360}, 70%, 75%)"
        for number, callable in enumerate(callables, 1)
    }
    producers = {
        feature: callable
        for callable in callables
        for feature in callable.output_features
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
        for callable in stage:
            entity = spec_definition.entities[callable.entity_id]
            dimensions = entity.dimension_ids
            columns = [
                DataLineageColumn(
                    name, spec_definition.dimensions[name].type, "Dimension", "#93c5fd", None
                )
                for name in dimensions
            ]
            for role, features in (
                (
                    "Declared input" if callable.operation == operations.ESCAPE else "Input",
                    callable.input_features,
                ),
                (
                    "Declared external output"
                    if callable.operation == operations.ESCAPE
                    else "Output",
                    callable.output_features,
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
                            producer is not None and producer.operation == operations.ESCAPE,
                        )
                    )
            dataset = entity.datasets.get(callable.dataset_id)
            steps.append(
                DataLineageStep(
                    number=numbers[callable.id],
                    callable_id=callable.id,
                    function=callable.function_id,
                    operation=callable.operation,
                    entity=callable.entity_id,
                    dataset=callable.dataset_id,
                    grain=dataset.row_scope.grain if dataset else "",
                    color=colors[callable.id],
                    columns=columns,
                    dependencies=sorted(
                        numbers[dependency] for dependency in callable.dependency_ids
                    ),
                )
            )
        stages.append(steps)
    return stages


def _create_website_page(
    spec_definition: spec.Spec,
    execution_plan: execution_plan.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = project.EXPLORER_INDEX_FILE.name,
    execution_scope: str = "all features",
    is_scoped: bool = False,
) -> None:
    """Write the linked data-lineage page from the already compiled plan.

    Args:
        spec_definition: Spec document model.
        execution_plan: Compiled plan; no analytical functions are called.
        output_directory: Directory shared by the website pages.
        index_filename: Filename of the website dashboard.
        execution_scope: Feature coverage of the rendered build.
        is_scoped: Whether the plan covers a selected feature subset.
    """
    document = (
        render.html_environment()
        .get_template("execution/data_lineage.html.j2")
        .render(
            stages=_build_stages(spec_definition, execution_plan),
            project_name=spec_definition.name,
            include_navigation=True,
            active_page="execution",
            active_section="lineage",
            root_path="../",
            index_filename=index_filename,
            execution_scope=execution_scope,
            is_scoped=is_scoped,
        )
    )
    target = output_directory / render.WEBSITE_PAGES["execution"]["lineage"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
