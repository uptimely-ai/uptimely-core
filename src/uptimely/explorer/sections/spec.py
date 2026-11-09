"""Prepare Explorer spec catalog data."""

from __future__ import annotations

import dataclasses
import datetime
import pathlib
import re
import typing
from importlib import util

import docstring_parser

from uptimely import entrypoint as entrypoint_module
from uptimely.spec import function_kinds, selectors
from uptimely.spec import model as spec_model

__all__ = [
    "ExplorerContext",
    "ExplorerSummary",
    "_build_context",
    "build_context",
    "_feature_data",
]


@dataclasses.dataclass(frozen=True)
class ExplorerSummary:
    """Typed summary values displayed in the explorer overview."""

    profile_count: int
    operator_count: int
    dimension_count: int
    feature_count: int
    bound_feature_count: int
    function_count: int
    feature_buckets: dict[str, int]
    vectorized_feature_count: int
    function_buckets: dict[str, int]


@dataclasses.dataclass(frozen=True)
class ExplorerContext:
    """Spec catalog metadata for one Explorer presentation."""

    configuration: dict[str, typing.Any]
    summary: ExplorerSummary
    feature_dependencies: list[dict[str, typing.Any]]
    generated_at: str | None = None


def build_context(
    context: ExplorerContext,
) -> dict[str, object]:
    """Prepare catalog data for the Explorer presentation.

    Args:
        context: Reference data shared with the Explorer presentation.

    Returns:
        Spec metadata and function groups for the catalog views.
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
    spec_definition: spec_model.Spec,
) -> tuple[list[dict], list[dict], set[str]]:
    """Collect operator-produced feature metadata and calculated feature references."""
    fragment_features: list[dict] = []
    calculated_features: list[dict] = []
    seen_inputs: set[tuple[str, str]] = set()
    for key, operator in spec_definition.operator_items:
        dataset = spec_definition.profiles_by_key[key[0]]
        function = spec_definition.functions.root.get(operator.compute.function)
        kind = function_kinds.FUNCTION_KINDS[function.kind] if function is not None else None
        for feature_id in operator.output_features:
            metadata = dataset.features.get(feature_id)
            feature = (
                metadata.model_dump(mode="json", exclude_none=True) if metadata is not None else {}
            )
            feature["id"] = feature_id
            if kind is not None and kind.is_transformer:
                calculated_features.append(
                    {
                        **feature,
                        "compute": operator.compute.model_dump(mode="json", exclude_none=True),
                        "inputs": operator.interface.inputs,
                    }
                )
            elif (dataset.id, feature_id) not in seen_inputs:
                fragment_features.append(feature)
                seen_inputs.add((dataset.id, feature_id))
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


def _format_examples(examples: typing.Iterable[docstring_parser.DocstringExample]) -> str:
    """Render parsed example fragments as plain Python code with output.

    Doctest prompts and doctest directive comments are removed so the
    example reads as an ordinary snippet.

    Args:
        examples: Parsed docstring examples with optional snippets and output.

    Returns:
        The cleaned example text.
    """
    text = "\n".join(
        part for example in examples for part in (example.snippet, example.description) if part
    )
    text = _DOCTEST_PROMPT.sub("", text)
    return _DOCTEST_DIRECTIVE.sub("", text).strip()


def _parse_docstring(docstring: str) -> dict[str, typing.Any] | None:
    """Parse a function docstring into structured documentation sections.

    Numpy-style section headers that a Google-style linter suffixed with a
    colon are normalized back before parsing.

    Args:
        docstring: Cleaned docstring text in any style docstring_parser detects.

    Returns:
        Parsed documentation sections, or None when the docstring cannot be parsed.
    """
    normalized = _SECTION_HEADER_COLON.sub(r"\1\2", docstring)
    try:
        parsed = docstring_parser.parse(normalized)
    except docstring_parser.ParseError:
        return None
    returns = parsed.returns
    if parsed.style == docstring_parser.DocstringStyle.NUMPYDOC:
        # NumPy's Examples section is one continuous narrative; the parser
        # splits it whenever a new prompt follows output or a continuation.
        examples = [_format_examples(parsed.examples)] if parsed.examples else []
    else:
        examples = [_format_examples([example]) for example in parsed.examples]
    return {
        "summary": parsed.short_description,
        "body": parsed.long_description,
        "params": {parameter.arg_name: parameter.description for parameter in parsed.params},
        "returns": (returns.description or returns.type_name) if returns else None,
        "raises": [
            {"type": error.type_name, "description": error.description} for error in parsed.raises
        ],
        "examples": examples,
    }


def _build_context(
    spec_definition: spec_model.Spec,
    include_generated_at: bool,
    project_root: pathlib.Path | None = None,
) -> ExplorerContext:
    """Build typed Explorer catalog data from a spec document model."""
    configuration = spec_definition.model_dump(mode="json", exclude_none=True)
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
            function["escape_operators"] = []
            function["operator_usage_count"] = 0
    for key, operator in spec_definition.operator_items:
        function = function_definitions[operator.compute.function]
        function["operator_usage_count"] = function.get("operator_usage_count", 0) + 1
        if function_kinds.FUNCTION_KINDS[function["kind"]].is_effect:
            function["escape_operators"].append(
                {
                    "profile": key[0],
                    "operator": operator.id,
                    "inputs": operator.input_features,
                    "outputs": operator.output_features,
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
            origin = function_entrypoint.read_source_origin(project_root)
            function["source_origin"] = origin.kind
            if origin.distribution is not None:
                function["source_distribution"] = origin.distribution
            return_type = function_entrypoint.function.read_signature().returns
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
    ) = _feature_data(spec_definition)
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
    profile_count = len(spec_definition.profiles)
    operator_count = sum(
        1
        for operator in spec_definition.operators
        if function_kinds.FUNCTION_KINDS[
            spec_definition.functions[operator.compute.function].kind
        ].is_source
    )
    summary = ExplorerSummary(
        profile_count=profile_count,
        operator_count=operator_count,
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
            "function": operator.compute.function,
            "kind": spec_definition.functions[operator.compute.function].kind,
            "feature": feature,
            "dependencies": operator.input_features,
        }
        for operator in spec_definition.operators
        if spec_definition.functions[operator.compute.function].kind
        in {function_kinds.ESCAPE, function_kinds.VECTORIZE}
        for feature in operator.output_features
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
