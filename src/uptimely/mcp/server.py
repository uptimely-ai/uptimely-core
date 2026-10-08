"""Serve specification introspection and feature execution over MCP.

The server exposes two layers of tools:

* Introspection over the function catalog and calculated features.
* Execution of a single calculated feature through the engine, which is the
  meaningful execution unit because vectorize functions build Polars
  expressions inside the dependency graph rather than returning data.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from uptimely.compile import Compiler, read_signature
from uptimely.engine import Engine
from uptimely.spec import Specification

logger = logging.getLogger(__name__)

FUNCTION_CATEGORIES = (
    "read",
    "write",
    "vectorize",
    "aggregate",
    "collapse",
    "expand",
    "conform",
)


@dataclass
class ServerState:
    """Runtime configuration and cached specification for the MCP server."""

    spec_path: Path
    project_root: Path
    runtime_resources: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    specification: Specification | None = field(default=None, repr=False)

    def load_specification(self, *, reload: bool = False) -> Specification:
        """Return the specification, parsing it on first use or when reloaded."""
        if self.specification is None or reload:
            self.specification = Specification.from_json(self.spec_path)
        return self.specification


def _to_json(payload: object) -> str:
    """Serialize a tool result as JSON."""
    return json.dumps(payload, indent=2)


def _collect_frame(value: object) -> Any:
    """Collect a Polars result into a concrete frame; pass other values through."""
    import polars as pl

    if isinstance(value, pl.LazyFrame):
        return value.collect()
    return value


def create_server(state: ServerState) -> FastMCP:
    """Create the MCP server with tools bound to the given server state."""
    project_root = str(state.project_root.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    mcp = FastMCP("uptimely")

    @mcp.tool()
    def list_functions() -> str:
        """List the function catalog: every function id grouped by category."""
        catalog = state.load_specification().function_catalog
        return _to_json(
            {category: sorted(getattr(catalog, category)) for category in FUNCTION_CATEGORIES}
        )

    @mcp.tool()
    def describe_function(category: str, function_id: str) -> str:
        """Describe one catalog function: entrypoint, declared args, Python signature.

        Args:
            category: Function category, one of: read, write, vectorize,
                aggregate, collapse, expand, conform.
            function_id: The function id from `list_functions`.
        """
        catalog = state.load_specification().function_catalog
        if category not in FUNCTION_CATEGORIES:
            raise ValueError(
                f"Unknown category: {category}. Expected one of: {', '.join(FUNCTION_CATEGORIES)}"
            )
        template = getattr(catalog, category).get(function_id)
        if template is None:
            raise ValueError(f"Unknown {category} function: {function_id}")
        signature = read_signature(template.entrypoint, root=state.project_root)
        return _to_json(
            {
                "id": function_id,
                "category": category,
                "entrypoint": template.entrypoint,
                "declared_args": {
                    name: {"type": argument.type, "comment": argument.comment}
                    for name, argument in template.args.items()
                },
                "python_signature": {
                    "args": signature.args,
                    "returns": signature.returns,
                },
            }
        )

    @mcp.tool()
    def list_calculated_features() -> str:
        """List calculated feature ids; each can be run with execute_feature."""
        specification = state.load_specification()
        payload = sorted(
            {
                feature_id
                for entity in specification.entities.values()
                for dataset in entity.datasets
                for feature_id in dataset.vectorize
            }
        )
        return _to_json(payload)

    @mcp.tool()
    def describe_feature(feature_id: str) -> str:
        """Show one calculated feature's dependencies.

        Args:
            feature_id: A calculated feature id from `list_calculated_features`.

        Returns:
            The producing function, the direct dependencies consumed by its
            binding, and the full transitive closure of calculated and input
            features needed to compute it.
        """
        specification = state.load_specification()
        by_feature = {call.feature: call for call in specification.calls}
        call = by_feature.get(feature_id)
        if call is None:
            raise ValueError(
                f"Unknown calculated feature: {feature_id}. "
                "Use list_calculated_features to see available features."
            )

        transitive: list[str] = []
        queue = list(call.depends_on_features)
        seen = set(queue)
        while queue:
            current = queue.pop(0)
            transitive.append(current)
            parent_call = by_feature.get(current)
            if parent_call is not None:
                for parent in parent_call.depends_on_features:
                    if parent not in seen:
                        seen.add(parent)
                        queue.append(parent)

        return _to_json(
            {
                "feature": feature_id,
                "entity": call.entity,
                "function": call.function,
                "direct_dependencies": call.depends_on_features,
                "transitive_dependencies": transitive,
                "input_features": [name for name in transitive if name not in by_feature],
                "calculated_dependencies": [name for name in transitive if name in by_feature],
            }
        )

    @mcp.tool()
    def compile_plan(feature_ids: list[str] | None = None) -> str:
        """Compile the specification and report plan stages and operation counts.

        Args:
            feature_ids: Optional subset of calculated features to compile;
                compiles the full specification when omitted.
        """
        specification = state.load_specification()
        plan = Compiler(specification, features=feature_ids).compile()
        return _to_json(
            {
                "features": feature_ids,
                "stages": [
                    [
                        {
                            "id": operation.id,
                            "kind": operation.kind,
                            "function_id": operation.function_id,
                        }
                        for operation in stage
                    ]
                    for stage in plan.execution_stages
                ],
                "operation_count": sum(len(stage) for stage in plan.execution_stages),
            }
        )

    @mcp.tool()
    def execute_feature(feature_id: str, max_rows: int = 50) -> str:
        """Run one calculated feature and return dimension-keyed rows.

        Args:
            feature_id: A calculated feature id from `list_calculated_features`.
            max_rows: Positive maximum number of rows included in the response.

        Returns:
            The computed values as JSON rows, or the engine failures. The
            dataset's configured sinks also run and may persist output.
        """
        if max_rows < 1:
            raise ValueError("max_rows must be a positive integer")

        specification = state.load_specification()
        plan = Compiler(specification, features=[feature_id]).compile()
        engine = Engine(
            specification,
            plan,
            runtime_resources=state.runtime_resources,
        )
        result = engine.execute()
        key = next((k for k in result.calculated_outputs if k[2] == feature_id), None)
        if key is None:
            return _to_json({"status": "failed", "failures": result.failures})
        entity_id, dataset_id, _ = key
        frame = _collect_frame(result.datasets.get((entity_id, dataset_id)))
        if frame is None or not hasattr(frame, "to_dicts"):
            return _to_json(
                {
                    "status": "ok",
                    "feature": feature_id,
                    "message": "Execution succeeded but produced no dataset for this feature.",
                }
            )
        entity = specification.entities.get(entity_id)
        columns = [
            name
            for name in [*(entity.dimensions if entity else []), feature_id]
            if name in frame.columns
        ]
        view = frame.select(columns) if columns else frame
        rows = view.head(max_rows).to_dicts()
        payload: dict[str, Any] = {
            "status": "ok",
            "feature": feature_id,
            "entity": entity_id,
            "dataset": dataset_id,
            "columns": view.columns,
            "row_count": len(rows),
            "rows": rows,
        }
        if result.failures:
            # Subset plans still run dataset sinks, which may need features
            # outside the subset; the calculation itself has already succeeded.
            payload["warnings"] = result.failures
        return _to_json(payload)

    @mcp.tool()
    def reload_specification() -> str:
        """Re-parse the specification file; use after editing the spec or functions."""
        specification = state.load_specification(reload=True)
        return _to_json(
            {
                "spec": str(state.spec_path),
                "entities": sorted(specification.entities),
                "functions": {
                    category: len(getattr(specification.function_catalog, category))
                    for category in FUNCTION_CATEGORIES
                },
            }
        )

    return mcp


def _load_runtime_resources(path: Path | None) -> dict[str, dict[str, dict[str, Any]]]:
    """Load a runtime resources mapping from a JSON file."""
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    """Launch the uptimely MCP server over stdio."""
    parser = argparse.ArgumentParser(description="Uptimely MCP server")
    parser.add_argument("--spec", required=True, type=Path, help="Path to the JSON specification")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Root added to sys.path so function entrypoints are importable",
    )
    parser.add_argument(
        "--runtime-resources",
        type=Path,
        default=None,
        help="JSON file with runtime resource values for ?storage-style placeholders",
    )
    args = parser.parse_args()

    # Log to stderr only: stdout is the MCP protocol channel.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("Starting uptimely MCP server for spec %s", args.spec)

    state = ServerState(
        spec_path=args.spec,
        project_root=args.project_root,
        runtime_resources=_load_runtime_resources(args.runtime_resources),
    )
    create_server(state).run()


if __name__ == "__main__":
    sys.exit(main())
