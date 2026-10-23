"""Build spec context and render explorer HTML pages."""

from __future__ import annotations

import dataclasses
import datetime
import pathlib
import typing
from importlib import util
from urllib import parse

from uptimely import contracts, project
from uptimely import entrypoint as entrypoint_module
from uptimely.spec import model as spec_model
from uptimely.spec import references

from . import render

SPEC_PAGES = render.WEBSITE_PAGES["spec"]
__all__ = [
    "SPEC_PAGES",
    "ExplorerContext",
    "ExplorerSummary",
    "_build_context",
    "_create_website_pages",
    "_feature_data",
    "_render_document",
]


@dataclasses.dataclass(frozen=True)
class ExplorerSummary:
    """Typed summary values displayed in the explorer overview."""

    entity_count: int
    dataset_count: int
    mapping_count: int
    dimension_count: int
    feature_count: int
    bound_feature_count: int
    function_count: int
    feature_buckets: dict[str, int]
    vectorized_feature_count: int
    function_buckets: dict[str, int]


@dataclasses.dataclass(frozen=True)
class ExplorerContext:
    """Complete template context for one explorer build."""

    configuration: dict[str, typing.Any]
    summary: ExplorerSummary
    feature_dependencies: list[dict[str, typing.Any]]
    generated_at: str | None = None


def _render_document(
    context: dict[str, typing.Any],
    output_path: pathlib.Path,
    section: str,
    index_filename: str,
    execution_scope: str,
    is_scoped: bool,
) -> pathlib.Path:
    """Write one spec section within the explorer website."""
    environment = render.html_environment()
    template = f"spec/{section}.html.j2"
    document = environment.get_template(template).render(
        configuration=context["configuration"],
        project_name=context["configuration"].get("name"),
        function_groups={
            operation: {
                function_id: function
                for function_id, function in context["configuration"]["functions"].items()
                if function.get("operation") == operation
            }
            for operation in contracts.FUNCTION_OPERATIONS
        },
        summary=context["summary"],
        feature_dependencies=context["feature_dependencies"],
        generated_at=context["generated_at"],
        include_navigation=True,
        active_page="spec",
        active_section=section,
        index_filename=index_filename,
        root_path="../",
        execution_scope=execution_scope,
        is_scoped=is_scoped,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def _create_website_pages(
    context: ExplorerContext,
    output_directory: pathlib.Path,
    *,
    index_filename: str = project.EXPLORER_INDEX_FILE.name,
    execution_scope: str = "all features",
    is_scoped: bool = False,
) -> None:
    """Export separate spec sections with shared website navigation.

    Args:
        context: Reference data shared with the website dashboard.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
        execution_scope: Feature coverage of the rendered build.
        is_scoped: Whether the plan covers a selected feature subset.
    """
    data = dataclasses.asdict(context)
    for section, filename in SPEC_PAGES.items():
        _render_document(
            data,
            output_directory / filename,
            section,
            index_filename,
            execution_scope,
            is_scoped,
        )


def _feature_data(
    configuration: dict[str, typing.Any],
) -> tuple[list[dict], list[dict], set[str], list[dict]]:
    """Collect mapped feature metadata and calculated feature references."""
    entities = configuration.get("entities", {})
    functions = configuration.get("functions", {})
    fragment_features: list[dict] = []
    calculated_features: list[dict] = []
    escape_features: list[dict] = []
    seen_inputs: set[tuple[str, str]] = set()
    for entity in entities.values():
        for dataset_id, dataset in entity.get("datasets", {}).items():
            for mapping in dataset.get("mappings", {}).values():
                function_id = mapping.get("binding", {}).get("function")
                function = functions.get(function_id, {})
                operation = function.get("operation")
                for reference in mapping.get("features", {}).get("outputs", []):
                    feature_id = reference.removeprefix(contracts.FEATURE_PREFIX)
                    feature = dict(dataset.get("features", {}).get(feature_id, {}))
                    feature["id"] = feature_id
                    if operation == "vectorize":
                        calculated_features.append(
                            {
                                **feature,
                                "binding": mapping.get("binding", {}),
                                "inputs": mapping.get("features", {}).get("inputs", []),
                            }
                        )
                    elif operation == "escape":
                        if (dataset_id, feature_id) not in seen_inputs:
                            escape_features.append(feature)
                            seen_inputs.add((dataset_id, feature_id))
                    elif (dataset_id, feature_id) not in seen_inputs:
                        fragment_features.append(feature)
                        seen_inputs.add((dataset_id, feature_id))
    referenced_features = {
        dependency
        for calculation in calculated_features
        for dependency in (
            reference.removeprefix(contracts.FEATURE_PREFIX)
            for reference in calculation.get("inputs", [])
        )
    }
    return fragment_features, calculated_features, referenced_features, escape_features


def _build_context(
    spec_definition: spec_model.Spec,
    include_generated_at: bool,
) -> ExplorerContext:
    """Build the typed template context from a spec document model."""
    configuration = spec_definition.model_dump(mode="json", exclude_none=True)
    entities = configuration.get("entities", {})
    dimensions = configuration.get("dimensions", {})
    function_definitions = configuration.get("functions", {})
    function_groups: dict[str, dict[str, dict[str, typing.Any]]] = {}
    for function_id, function in function_definitions.items():
        if not isinstance(function, dict):
            continue
        operation = function.get("operation")
        if isinstance(operation, str):
            function_groups.setdefault(operation, {})[function_id] = function
            function["declared_returns"] = contracts.OPERATION_RETURN_KINDS[operation]
            function["escape_mappings"] = []
    for entity_id, dataset, mapping in references.iter_mappings(spec_definition):
        function = function_definitions[mapping.binding.function]
        if function.get("operation") == "escape":
            function["escape_mappings"].append(
                {
                    "entity": entity_id,
                    "dataset": dataset.id,
                    "mapping": mapping.id,
                    "inputs": mapping.input_features,
                    "outputs": mapping.output_features,
                }
            )
    for function in function_definitions.values():
        if not isinstance(function, dict):
            continue
        validate_signature = function.get("validate_signature", True)
        function["signature_validation_disabled"] = not validate_signature
        entrypoint = function.get("entrypoint")
        if not isinstance(entrypoint, str) or ":" not in entrypoint:
            continue
        module_name = entrypoint.rsplit(":", 1)[0]
        if parse.urlsplit(module_name).scheme in entrypoint_module.REMOTE_SCHEMES:
            function["entrypoint_file"] = module_name
        elif pathlib.Path(module_name).is_file():
            function["entrypoint_file"] = pathlib.Path(module_name).resolve().as_uri()
        elif validate_signature:
            try:
                module_spec = util.find_spec(module_name.removesuffix(".py").replace("/", "."))
            except (ModuleNotFoundError, ValueError):
                module_spec = None
            if module_spec is not None and module_spec.origin not in (
                None,
                "built-in",
                "frozen",
            ):
                function["entrypoint_file"] = pathlib.Path(module_spec.origin).resolve().as_uri()
        if validate_signature:
            return_type = entrypoint_module.Entrypoint(
                entrypoint, pathlib.Path.cwd()
            ).function.signature.returns
            if return_type:
                function["return_type"] = return_type
    (
        fragment_features,
        calculated_features,
        referenced_features,
        escape_features,
    ) = _feature_data(configuration)
    feature_buckets = {
        "input": len(fragment_features),
        "intermediate": sum(
            calculation["id"] in referenced_features for calculation in calculated_features
        ),
        "output": sum(
            calculation["id"] not in referenced_features for calculation in calculated_features
        ),
        "external": len(escape_features),
    }
    function_buckets = {
        operation: len(function_groups.get(operation, {}))
        for operation in contracts.FUNCTION_OPERATIONS
    }
    dataset_count = sum(len(entity.get("datasets", {})) for entity in entities.values())
    mapping_count = sum(
        1
        for entity in entities.values()
        for dataset in entity.get("datasets", {}).values()
        for mapping in dataset.get("mappings", {}).values()
        if any(
            mapping.get("binding", {}).get("function") in function_groups.get(operation, {})
            for operation in contracts.FRAGMENT_OPERATIONS
        )
    )
    summary = ExplorerSummary(
        entity_count=len(entities),
        dataset_count=dataset_count,
        mapping_count=mapping_count,
        dimension_count=len(dimensions),
        feature_count=len([*fragment_features, *calculated_features, *escape_features]),
        bound_feature_count=len(calculated_features),
        function_count=sum(
            len(group) for group in function_groups.values() if isinstance(group, dict)
        ),
        feature_buckets=feature_buckets,
        vectorized_feature_count=feature_buckets["intermediate"] + feature_buckets["output"],
        function_buckets=function_buckets,
    )
    dependencies = [
        {
            "function": mapping.binding.function,
            "operation": spec_definition.functions[mapping.binding.function].operation,
            "feature": feature,
            "dependencies": mapping.input_features,
        }
        for _entity_id, _dataset, mapping in references.iter_mappings(spec_definition)
        if spec_definition.functions[mapping.binding.function].operation in {"escape", "vectorize"}
        for feature in mapping.output_features
    ]
    generated_at = (
        datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        if include_generated_at
        else None
    )
    return ExplorerContext(
        configuration=configuration,
        summary=summary,
        feature_dependencies=dependencies,
        generated_at=generated_at,
    )
