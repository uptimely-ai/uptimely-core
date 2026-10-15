"""Render processing tables and their dependencies without executing analytics."""

from __future__ import annotations

import dataclasses
import pathlib

from uptimely import analytics, plan, render


@dataclasses.dataclass(frozen=True)
class DataLineageColumn:
    """A declared column, its role, and its producing step."""

    name: str
    type: str
    role: str
    color: str
    producer: int | None


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
    analytics_definition: analytics.Analytics, execution_plan: plan.ExecutionPlan
) -> list[list[DataLineageStep]]:
    """Build typed table schemas with colors inherited from feature producers.

    Args:
        analytics_definition: Declared dimensions, datasets, and column metadata.
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
        if feature not in analytics_definition.dimensions
    }
    datasets = {
        dataset.id: dataset
        for entity in analytics_definition.entities.values()
        for dataset in entity.datasets
    }
    feature_types = {
        name: feature.type or "Unspecified"
        for dataset in datasets.values()
        for name, feature in dataset.features.items()
        if name not in analytics_definition.dimensions
    }
    feature_types.update(
        {name: dimension.type for name, dimension in analytics_definition.dimensions.items()}
    )
    stages: list[list[DataLineageStep]] = []
    for stage in ordered_stages:
        steps: list[DataLineageStep] = []
        for callable in stage:
            dimensions = analytics_definition.entities[callable.entity_id].dimension_ids
            columns = [
                DataLineageColumn(
                    name, analytics_definition.dimensions[name].type, "Dimension", "#93c5fd", None
                )
                for name in dimensions
            ]
            for role, features in (
                ("Input", callable.input_features),
                ("Output", callable.output_features),
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
                            if feature in analytics_definition.dimensions
                            else "#cbd5e1",
                            numbers[producer.id] if producer else None,
                        )
                    )
            dataset = datasets.get(callable.dataset_id)
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
    analytics_definition: analytics.Analytics,
    execution_plan: plan.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = "index.html",
) -> None:
    """Write the linked data-lineage page from the already compiled plan.

    Args:
        analytics_definition: Canonical analytics model.
        execution_plan: Compiled plan; no analytical functions are called.
        output_directory: Directory shared by the website pages.
        index_filename: Filename of the website dashboard.
    """
    document = (
        render.html_environment()
        .get_template("execution/data_lineage.html.j2")
        .render(
            stages=_build_stages(analytics_definition, execution_plan),
            include_navigation=True,
            active_page="execution",
            active_section="lineage",
            root_path="../",
            index_filename=index_filename,
        )
    )
    target = output_directory / render.WEBSITE_PAGES["execution"]["lineage"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
