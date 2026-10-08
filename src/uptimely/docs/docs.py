"""Generate deterministic documentation data and HTML from canonical specifications."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from uptimely.compile.entrypoint import read_signature
from uptimely.spec import Specification
from uptimely.spec.json_spec.bindings import feature_dependencies

OUTPUT_DIR = Path("generated")


@dataclass(frozen=True)
class DocumentationSummary:
    """Typed summary values displayed in the documentation overview."""

    entity_count: int
    dataset_count: int
    fragment_count: int
    dimension_count: int
    feature_count: int
    bound_feature_count: int
    function_count: int
    feature_buckets: dict[str, int]
    vectorized_feature_count: int
    function_buckets: dict[str, int]


@dataclass(frozen=True)
class DocumentationContext:
    """Complete template context for one documentation build."""

    configuration: dict[str, Any]
    summary: DocumentationSummary
    feature_dependencies: list[dict[str, Any]]
    generated_at: str | None = None


def _write_document_data(context: DocumentationContext, output_path: Path) -> dict[str, Any]:
    data = asdict(context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return data


def _render_document(context: dict[str, Any], output_path: Path) -> Path:
    environment = Environment(
        loader=PackageLoader("uptimely", "docs/templates"),
        autoescape=select_autoescape(["html"]),
    )
    document = environment.get_template("docs.html.j2").render(
        configuration=context["configuration"],
        summary=context["summary"],
        feature_dependencies=context["feature_dependencies"],
        generated_at=context["generated_at"],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def _feature_data(configuration: dict[str, Any]) -> tuple[list[dict], list[dict], set[str]]:
    """Collect declared features and calculated feature references."""
    entities = configuration.get("entities", {})
    fragment_features = [
        feature
        for entity in entities.values()
        for dataset in entity.get("datasets", [])
        for operation_type in ("read", "conform", "expand", "collapse")
        for fragment in dataset.get(operation_type, {}).values()
        for feature in fragment.get("features", {}).values()
    ]
    calculated_features = [
        calculation
        for entity in entities.values()
        for dataset in entity.get("datasets", [])
        for calculation in dataset.get("vectorize", {}).values()
    ]
    referenced_features = {
        dependency
        for calculation in calculated_features
        for dependency in feature_dependencies((calculation.get("binding") or {}).get("args"))
    }
    return fragment_features, calculated_features, referenced_features


def _build_context(
    specification: Specification, include_generated_at: bool
) -> DocumentationContext:
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
            module_name = entrypoint.split(":", 1)[0]
            try:
                module_spec = importlib.util.find_spec(module_name)
            except (ModuleNotFoundError, ValueError):
                module_spec = None
            if module_spec is not None and module_spec.origin not in (None, "built-in", "frozen"):
                function["entrypoint_file"] = Path(module_spec.origin).resolve().as_uri()
            try:
                return_type = read_signature(entrypoint, Path.cwd()).returns
            except (AttributeError, ImportError, ModuleNotFoundError, TypeError, ValueError):
                return_type = None
            if return_type:
                function["return_type"] = return_type
    fragment_features, calculated_features, referenced_features = _feature_data(configuration)
    feature_buckets = {
        "input": len(fragment_features),
        "intermediate": sum(
            calculation_id in referenced_features
            for entity in entities.values()
            for dataset in entity.get("datasets", [])
            for calculation_id in dataset.get("vectorize", {})
        ),
        "output": sum(
            calculation_id not in referenced_features
            for entity in entities.values()
            for dataset in entity.get("datasets", [])
            for calculation_id in dataset.get("vectorize", {})
        ),
    }
    function_buckets = {
        group_name: len(function_groups.get(group_name, {}))
        if isinstance(function_groups.get(group_name, {}), dict)
        else 0
        for group_name in ("read", "write", "vectorize", "aggregate")
    }
    dataset_count = sum(len(entity.get("datasets", [])) for entity in entities.values())
    fragment_count = sum(
        len(dataset.get(operation_type, {}))
        for entity in entities.values()
        for dataset in entity.get("datasets", [])
        for operation_type in ("read", "conform", "expand", "collapse")
    )
    summary = DocumentationSummary(
        entity_count=len(entities),
        dataset_count=dataset_count,
        fragment_count=fragment_count,
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
            "dependencies": feature_dependencies(call.args),
        }
        for call in specification.calls
    ]
    generated_at = (
        datetime.now().astimezone().isoformat(timespec="seconds") if include_generated_at else None
    )
    return DocumentationContext(
        configuration=configuration,
        summary=summary,
        feature_dependencies=dependencies,
        generated_at=generated_at,
    )


class Documentation:
    """Create documentation from a canonical specification."""

    def __init__(self, specification: Specification):
        self.spec = specification

    def create_json(
        self,
        output_path: str | Path | None = None,
        include_generated_at: bool = False,
    ) -> Path:
        """Export documentation data as JSON."""
        target = Path(output_path) if output_path is not None else OUTPUT_DIR / "docs.json"
        target = target.with_suffix(".json")
        context = _build_context(self.spec, include_generated_at)
        _write_document_data(context, target)
        return target

    def create_html(
        self,
        output_path: str | Path | None = None,
        include_generated_at: bool = False,
    ) -> Path:
        """Render documentation as HTML."""
        target = Path(output_path) if output_path is not None else OUTPUT_DIR / "docs.html"
        context = asdict(_build_context(self.spec, include_generated_at))
        return _render_document(context, target.with_suffix(".html"))


def create_json(
    specification: Specification,
    output_path: str | Path | None = None,
    include_generated_at: bool = False,
) -> Path:
    """Export documentation data as JSON."""
    return Documentation(specification).create_json(
        output_path=output_path,
        include_generated_at=include_generated_at,
    )


def create_html(
    specification: Specification,
    output_path: str | Path | None = None,
    include_generated_at: bool = False,
) -> Path:
    """Render documentation as HTML."""
    return Documentation(specification).create_html(
        output_path=output_path,
        include_generated_at=include_generated_at,
    )
