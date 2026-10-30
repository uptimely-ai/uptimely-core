"""Build spec context and render explorer HTML pages."""

from __future__ import annotations

import dataclasses
import datetime
import pathlib
import re
import typing
from importlib import util

import docstring_parser

from uptimely import entrypoint as entrypoint_module
from uptimely.explorer import render
from uptimely.spec import functions as function_kinds
from uptimely.spec import model as spec_model
from uptimely.spec import references, selectors

SPEC_PAGES = render.WEBSITE_PAGES["spec"]
SPEC_CONTENT_PAGES = {
    section: filename for section, filename in SPEC_PAGES.items() if section != "feature_lineage"
}
SECTION = render.WebsiteSection(
    active_page="spec",
    pages=tuple(
        render.WebsitePage(f"spec/{section}.html.j2", filename, active_section=section)
        for section, filename in SPEC_CONTENT_PAGES.items()
    ),
)
__all__ = [
    "SPEC_PAGES",
    "ExplorerContext",
    "ExplorerSummary",
    "_build_context",
    "SECTION",
    "build_context",
    "_feature_data",
]


@dataclasses.dataclass(frozen=True)
class ExplorerSummary:
    """Typed summary values displayed in the explorer overview."""

    entity_count: int
    dataset_count: int
    action_count: int
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


def build_context(
    context: ExplorerContext,
) -> dict[str, object]:
    """Prepare display data shared by the spec pages.

    Args:
        context: Reference data shared with the website dashboard.

    Returns:
        Spec metadata and function groups for the section templates.
    """
    data = dataclasses.asdict(context)
    data["function_groups"] = {
        kind: {
            function_id: function
            for function_id, function in context.configuration["functions"].items()
            if function.get("kind") == kind
        }
        for kind in function_kinds.FUNCTION_KINDS
    }
    return data


def _feature_data(
    configuration: dict[str, typing.Any],
) -> tuple[list[dict], list[dict], set[str]]:
    """Collect action-produced feature metadata and calculated feature references."""
    entities = configuration.get("entities", {})
    functions = configuration.get("functions", {})
    fragment_features: list[dict] = []
    calculated_features: list[dict] = []
    seen_inputs: set[tuple[str, str]] = set()
    for entity in entities.values():
        for dataset_id, dataset in entity.get("datasets", {}).items():
            for action in dataset.get("actions", {}).values():
                function_id = action.get("binding", {}).get("function")
                function = functions.get(function_id, {})
                kind = function.get("kind")
                for reference in action.get("features", {}).get("outputs", []):
                    feature_id = reference.removeprefix(selectors.FEATURE_PREFIX)
                    feature = dict(dataset.get("features", {}).get(feature_id, {}))
                    feature["id"] = feature_id
                    if kind == function_kinds.VECTORIZE:
                        calculated_features.append(
                            {
                                **feature,
                                "binding": action.get("binding", {}),
                                "inputs": action.get("features", {}).get("inputs", []),
                            }
                        )
                    elif (dataset_id, feature_id) not in seen_inputs:
                        fragment_features.append(feature)
                        seen_inputs.add((dataset_id, feature_id))
    referenced_features = {
        dependency
        for calculation in calculated_features
        for dependency in (
            reference.removeprefix(selectors.FEATURE_PREFIX)
            for reference in calculation.get("inputs", [])
        )
    }
    return fragment_features, calculated_features, referenced_features


_SECTION_HEADER_COLON = re.compile(r"^([A-Z][A-Za-z ]*):(\n-+)$", flags=re.MULTILINE)
_DOCTEST_PROMPT = re.compile(r"^(?:>>>|\.\.\.) ?", flags=re.MULTILINE)
_DOCTEST_DIRECTIVE = re.compile(r"[ \t]*#[ \t]*doctest:.*$", flags=re.MULTILINE)


def _format_example(example: docstring_parser.DocstringExample) -> str:
    """Render a parsed docstring example as plain Python code with output.

    Doctest prompts and doctest directive comments are removed so the
    example reads as an ordinary snippet.

    Args:
        example: Parsed docstring example with an optional snippet and output.

    Returns:
        The cleaned example text.
    """
    text = "\n".join(part for part in (example.snippet, example.description) if part)
    text = _DOCTEST_PROMPT.sub("", text)
    return _DOCTEST_DIRECTIVE.sub("", text).strip()


def _parse_docstring(docstring: str) -> dict[str, typing.Any] | None:
    """Parse a function docstring into template-ready documentation sections.

    Numpy-style section headers that a Google-style linter suffixed with a
    colon are normalized back before parsing.

    Args:
        docstring: Cleaned docstring text in any style docstring_parser detects.

    Returns:
        Documentation sections for the function card, or None when the
        docstring cannot be parsed.
    """
    normalized = _SECTION_HEADER_COLON.sub(r"\1\2", docstring)
    try:
        parsed = docstring_parser.parse(normalized)
    except docstring_parser.ParseError:
        return None
    returns = parsed.returns
    return {
        "summary": parsed.short_description,
        "body": parsed.long_description,
        "params": {parameter.arg_name: parameter.description for parameter in parsed.params},
        "returns": (returns.description or returns.type_name) if returns else None,
        "raises": [
            {"type": error.type_name, "description": error.description} for error in parsed.raises
        ],
        "examples": [_format_example(example) for example in parsed.examples],
    }


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
        kind = function.get("kind")
        if isinstance(kind, str):
            function_groups.setdefault(kind, {})[function_id] = function
            function["declared_returns"] = function_kinds.FUNCTION_KINDS[kind].returns
            function["escape_actions"] = []
            function["action_usage_count"] = 0
    for entity_id, dataset, action in references.iter_actions(spec_definition):
        function = function_definitions[action.binding.function]
        function["action_usage_count"] = function.get("action_usage_count", 0) + 1
        if function.get("kind") == function_kinds.ESCAPE:
            function["escape_actions"].append(
                {
                    "entity": entity_id,
                    "dataset": dataset.id,
                    "action": action.id,
                    "inputs": action.input_features,
                    "outputs": action.output_features,
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
        if validate_signature:
            try:
                module_spec = util.find_spec(module_name)
            except (ModuleNotFoundError, ValueError):
                module_spec = None
            if module_spec is not None and module_spec.origin not in (
                None,
                "built-in",
                "frozen",
            ):
                function["entrypoint_file"] = pathlib.Path(module_spec.origin).resolve().as_uri()
        if validate_signature:
            function_entrypoint = entrypoint_module.Entrypoint(entrypoint)
            source_file = function_entrypoint.module.source_file
            function["entrypoint_file"] = pathlib.Path(source_file).resolve().as_uri()
            return_type = function_entrypoint.function.signature.returns
            if return_type:
                function["return_type"] = return_type
            docstring = function_entrypoint.function.docstring
            documentation = _parse_docstring(docstring) if docstring else None
            if documentation:
                function["doc"] = documentation
                if not function.get("description"):
                    function["description"] = documentation["summary"]
    (
        fragment_features,
        calculated_features,
        referenced_features,
    ) = _feature_data(configuration)
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
        kind: len(function_groups.get(kind, {})) for kind in function_kinds.FUNCTION_KINDS
    }
    dataset_count = sum(len(entity.get("datasets", {})) for entity in entities.values())
    action_count = sum(
        1
        for entity in entities.values()
        for dataset in entity.get("datasets", {}).values()
        for action in dataset.get("actions", {}).values()
        if any(
            action.get("binding", {}).get("function") in function_groups.get(kind, {})
            for kind, definition in function_kinds.FUNCTION_KINDS.items()
            if definition.is_source
        )
    )
    summary = ExplorerSummary(
        entity_count=len(entities),
        dataset_count=dataset_count,
        action_count=action_count,
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
            "function": action.binding.function,
            "kind": spec_definition.functions[action.binding.function].kind,
            "feature": feature,
            "dependencies": action.input_features,
        }
        for _, _, action in references.iter_actions(spec_definition)
        if spec_definition.functions[action.binding.function].kind
        in {function_kinds.ESCAPE, function_kinds.VECTORIZE}
        for feature in action.output_features
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
