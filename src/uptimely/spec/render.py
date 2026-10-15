"""Generate deterministic reference data and HTML from canonical specifications."""

from __future__ import annotations

import dataclasses
import datetime
import json
import pathlib
import typing
from importlib import util
from urllib import parse

from uptimely import render, spec
from uptimely.compile import entrypoint as compile_entrypoint

OUTPUT_DIR = pathlib.Path("_generated") / "spec"
SPECIFICATION_PAGES = render.WEBSITE_PAGES["spec"]


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


def _write_document_data(
    context: ExplorerContext, output_path: pathlib.Path
) -> dict[str, typing.Any]:
    data = dataclasses.asdict(context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return data


def _render_document(
    context: dict[str, typing.Any],
    output_path: pathlib.Path,
    section: str,
    index_filename: str,
) -> pathlib.Path:
    """Write one specification section within the explorer website."""
    environment = render.html_environment()
    template = f"spec/{section}.html.j2"
    document = environment.get_template(template).render(
        configuration=context["configuration"],
        summary=context["summary"],
        feature_dependencies=context["feature_dependencies"],
        generated_at=context["generated_at"],
        include_navigation=True,
        active_page="spec",
        active_section=section,
        index_filename=index_filename,
        root_path="../",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def _create_website_pages(
    context: ExplorerContext,
    output_directory: pathlib.Path,
    *,
    index_filename: str = "index.html",
) -> None:
    """Export separate specification sections with shared website navigation.

    Args:
        context: Reference data shared with the website dashboard.
        output_directory: Directory shared by all website pages.
        index_filename: Filename of the website dashboard.
    """
    data = dataclasses.asdict(context)
    for section, filename in SPECIFICATION_PAGES.items():
        _render_document(data, output_directory / filename, section, index_filename)


def _feature_data(configuration: dict[str, typing.Any]) -> tuple[list[dict], list[dict], set[str]]:
    """Collect mapped feature metadata and calculated feature references."""
    entities = configuration.get("entities", {})
    functions = configuration.get("functions", {})
    fragment_features: list[dict] = []
    calculated_features: list[dict] = []
    seen_inputs: set[tuple[str, str]] = set()
    for entity in entities.values():
        for dataset in entity.get("datasets", []):
            for mapping in dataset.get("mappings", {}).values():
                function_id = mapping.get("binding", {}).get("function")
                category = next(
                    (
                        name
                        for name in (
                            "read",
                            "conform",
                            "expand",
                            "collapse",
                            "vectorize",
                            "write",
                        )
                        if function_id in functions.get(name, {})
                    ),
                    None,
                )
                for reference in mapping.get("features", {}).get("outputs", []):
                    feature_id = reference.removeprefix("$features.")
                    feature = dict(dataset.get("features", {}).get(feature_id, {}))
                    feature["id"] = feature_id
                    if category == "vectorize":
                        calculated_features.append(
                            {
                                **feature,
                                "binding": mapping.get("binding", {}),
                                "inputs": mapping.get("features", {}).get("inputs", []),
                            }
                        )
                    elif (dataset.get("id", ""), feature_id) not in seen_inputs:
                        fragment_features.append(feature)
                        seen_inputs.add((dataset.get("id", ""), feature_id))
    referenced_features = {
        dependency
        for calculation in calculated_features
        for dependency in (
            reference.removeprefix("$features.") for reference in calculation.get("inputs", [])
        )
    }
    return fragment_features, calculated_features, referenced_features


def _build_context(
    specification: spec.Specification, include_generated_at: bool
) -> ExplorerContext:
    """Build the typed template context from a canonical specification model."""
    configuration = specification.model_dump(mode="json", exclude_none=True)
    for entity_id, entity in specification.entities.items():
        serialized_entity = configuration.get("entities", {}).get(entity_id)
        if not isinstance(serialized_entity, dict):
            continue
        datasets = serialized_entity.get("datasets", [])
        for index, dataset in enumerate(entity.datasets):
            if index < len(datasets) and isinstance(datasets[index], dict):
                datasets[index]["id"] = dataset.id
    entities = configuration.get("entities", {})
    dimensions = configuration.get("dimensions", {})
    function_groups = configuration.get("functions", {})
    for group in function_groups.values():
        if not isinstance(group, dict):
            continue
        for function in group.values():
            if not isinstance(function, dict):
                continue
            entrypoint = function.get("entrypoint")
            if not isinstance(entrypoint, str) or ":" not in entrypoint:
                continue
            module_name = entrypoint.rsplit(":", 1)[0]
            if parse.urlsplit(module_name).scheme in compile_entrypoint.REMOTE_SCHEMES:
                function["entrypoint_file"] = module_name
            elif pathlib.Path(module_name).is_file():
                function["entrypoint_file"] = pathlib.Path(module_name).resolve().as_uri()
            else:
                try:
                    module_spec = util.find_spec(module_name.removesuffix(".py").replace("/", "."))
                except (ModuleNotFoundError, ValueError):
                    module_spec = None
                if module_spec is not None and module_spec.origin not in (
                    None,
                    "built-in",
                    "frozen",
                ):
                    function["entrypoint_file"] = (
                        pathlib.Path(module_spec.origin).resolve().as_uri()
                    )
            try:
                return_type = compile_entrypoint.read_signature(
                    entrypoint, pathlib.Path.cwd()
                ).returns
            except (AttributeError, ImportError, ModuleNotFoundError, TypeError, ValueError):
                return_type = None
            if return_type:
                function["return_type"] = return_type
    fragment_features, calculated_features, referenced_features = _feature_data(configuration)
    feature_buckets = {
        "input": len(fragment_features),
        "intermediate": sum(
            calculation["id"] in referenced_features for calculation in calculated_features
        ),
        "output": sum(
            calculation["id"] not in referenced_features for calculation in calculated_features
        ),
    }
    function_buckets = {
        group_name: len(function_groups.get(group_name, {}))
        if isinstance(function_groups.get(group_name, {}), dict)
        else 0
        for group_name in ("read", "write", "vectorize", "collapse", "expand", "conform")
    }
    dataset_count = sum(len(entity.get("datasets", [])) for entity in entities.values())
    mapping_count = sum(
        1
        for entity in entities.values()
        for dataset in entity.get("datasets", [])
        for mapping in dataset.get("mappings", {}).values()
        if any(
            mapping.get("binding", {}).get("function") in function_groups.get(category, {})
            for category in ("read", "conform", "expand", "collapse")
        )
    )
    summary = ExplorerSummary(
        entity_count=len(entities),
        dataset_count=dataset_count,
        mapping_count=mapping_count,
        dimension_count=len(dimensions),
        feature_count=len([*fragment_features, *calculated_features]),
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
            "function": call.function,
            "feature": call.feature,
            "dependencies": call.depends_on_features,
        }
        for call in specification.calls
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


def create_json(
    specification: spec.Specification,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Export specification reference data as JSON.

    Args:
        specification: The canonical analytics specification.
        output_path: Destination for the reference data.
        include_generated_at: Include a build timestamp.

    Returns:
        The path to the written JSON document.
    """
    target = pathlib.Path(output_path) if output_path is not None else OUTPUT_DIR / "docs.json"
    context = _build_context(specification, include_generated_at)
    target = target.with_suffix(".json")
    _write_document_data(context, target)
    return target
