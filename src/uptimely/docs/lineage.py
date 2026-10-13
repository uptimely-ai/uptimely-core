"""Render processing tables and their dependencies without executing analytics."""

from __future__ import annotations

import dataclasses
import pathlib

from uptimely import plan, render, spec


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
    operation_id: str
    function: str
    kind: str
    entity: str
    dataset: str | None
    grain: str
    color: str
    columns: list[DataLineageColumn]
    dependencies: list[int]


def _build_stages(
    specification: spec.Specification, execution_plan: plan.ExecutionPlan
) -> list[list[DataLineageStep]]:
    """Build typed table schemas with colors inherited from feature producers.

    Args:
        specification: Declared dimensions, datasets, and column metadata.
        execution_plan: Compiled operations and their dependencies.

    Returns:
        Processing tables grouped by dependency stage.
    """
    ordered_stages = [
        sorted(stage, key=lambda operation: operation.id)
        for stage in execution_plan.execution_stages
    ]
    operations = [operation for stage in ordered_stages for operation in stage]
    numbers = {operation.id: number for number, operation in enumerate(operations, 1)}
    colors = {
        operation.id: f"hsl({(150 + number * 137) % 360}, 70%, 75%)"
        for number, operation in enumerate(operations, 1)
    }
    producers = {
        feature: operation
        for operation in operations
        for feature in operation.output_features
        if feature not in specification.dimensions
    }
    datasets = {
        dataset.id: dataset
        for entity in specification.entities.values()
        for dataset in entity.datasets
    }
    feature_types = {
        name: feature.type or "Unspecified"
        for dataset in datasets.values()
        for name, feature in dataset.features.items()
        if name not in specification.dimensions
    }
    feature_types.update(
        {name: dimension.type for name, dimension in specification.dimensions.items()}
    )
    stages: list[list[DataLineageStep]] = []
    for stage in ordered_stages:
        steps: list[DataLineageStep] = []
        for operation in stage:
            dimensions = specification.entities[operation.entity_id].dimensions
            columns = [
                DataLineageColumn(
                    name, specification.dimensions[name].type, "Dimension", "#93c5fd", None
                )
                for name in dimensions
            ]
            for role, features in (
                ("Input", operation.input_features),
                ("Output", operation.output_features),
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
                            if feature in specification.dimensions
                            else "#cbd5e1",
                            numbers[producer.id] if producer else None,
                        )
                    )
            dataset = datasets.get(operation.dataset_id)
            steps.append(
                DataLineageStep(
                    number=numbers[operation.id],
                    operation_id=operation.id,
                    function=operation.function_id,
                    kind=operation.kind,
                    entity=operation.entity_id,
                    dataset=operation.dataset_id,
                    grain=dataset.row_scope.grain if dataset else "",
                    color=colors[operation.id],
                    columns=columns,
                    dependencies=sorted(
                        numbers[dependency] for dependency in operation.dependency_ids
                    ),
                )
            )
        stages.append(steps)
    return stages


def _create_website_page(
    specification: spec.Specification,
    execution_plan: plan.ExecutionPlan,
    output_directory: pathlib.Path,
    *,
    index_filename: str = "index.html",
) -> None:
    """Write the linked data-lineage page from the already compiled plan.

    Args:
        specification: Canonical analytics specification.
        execution_plan: Compiled plan; no analytical functions are called.
        output_directory: Directory shared by the website pages.
        index_filename: Filename of the website dashboard.
    """
    document = (
        render.html_environment()
        .get_template("execution/data_lineage.html.j2")
        .render(
            stages=_build_stages(specification, execution_plan),
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
