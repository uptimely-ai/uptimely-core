"""Serve spec introspection and feature execution over MCP.

The server exposes two layers of tools:

* Introspection over the function catalog and calculated features.
* Execution of a calculated feature and its explicit prerequisites through
  dimension-keyed dataframe-producing mappings.
"""

import argparse
import dataclasses
import datetime
import json
import logging
import pathlib
import sys
import typing

import fastmcp
import polars as pl

from uptimely import compiler, entrypoint, spec
from uptimely import engine as uptimely_engine
from uptimely.spec import model as spec_model

logger = logging.getLogger(__name__)

FUNCTION_OPERATIONS = spec_model.FUNCTION_OPERATIONS


@dataclasses.dataclass
class ServerState:
    """Engine configuration, runtime bindings, and cached spec."""

    spec_path: pathlib.Path
    project_root: pathlib.Path
    engine_config: uptimely_engine.EngineConfig = dataclasses.field(
        default_factory=uptimely_engine.EngineConfig
    )
    bind: dict[str, dict[str, dict[str, typing.Any]]] = dataclasses.field(default_factory=dict)
    spec: spec_model.Spec | None = dataclasses.field(default=None, repr=False)

    def load_spec(self, *, reload: bool = False) -> spec_model.Spec:
        """Return spec, parsing it on first use or when reloaded."""
        if self.spec is None or reload:
            self.spec = spec.load_spec(self.spec_path)
        return self.spec


def _to_json(payload: object) -> str:
    """Serialize a tool result as JSON."""

    def serialize(value: object) -> str:
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    return json.dumps(payload, indent=2, default=serialize)


def _collect_frame(value: object) -> typing.Any:
    """Collect a Polars result into a concrete frame; pass other values through."""
    if isinstance(value, pl.LazyFrame):
        return value.collect()
    return value


def create_server(state: ServerState) -> fastmcp.FastMCP:
    """Create the MCP server with tools bound to the given server state."""
    project_root = str(state.project_root.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    mcp = fastmcp.FastMCP("uptimely")

    @mcp.tool()
    def list_functions() -> str:
        """List every function id and its operation."""
        catalog = state.load_spec().functions
        return _to_json(
            [
                {"id": function_id, "operation": function.operation}
                for function_id, function in sorted(catalog.root.items())
            ]
        )

    @mcp.tool()
    def describe_function(function_id: str) -> str:
        """Describe one catalog function: entrypoint, declared args, Python signature.

        Args:
            function_id: The function id from `list_functions`.
        """
        catalog = state.load_spec().functions
        template = catalog.get(function_id)
        if template is None:
            raise ValueError(f"Unknown function: {function_id}")
        signature = entrypoint.read_signature(template.entrypoint, root=state.project_root)
        return _to_json(
            {
                "id": function_id,
                "operation": template.operation,
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
        spec_definition = state.load_spec()
        payload = sorted(
            {
                feature_id
                for entity in spec_definition.entities.values()
                for dataset in entity.datasets
                for mapping in dataset.mappings.values()
                if hasattr(mapping, "binding")
                if (
                    mapping.binding.function in spec_definition.functions
                    and spec_definition.functions[mapping.binding.function].operation == "vectorize"
                )
                for feature_id in mapping.output_features
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
        spec_definition = state.load_spec()
        by_feature = {call.feature: call for call in spec.prepare_spec(spec_definition).calls}
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
        """Compile spec and report plan stages and operation counts.

        Args:
            feature_ids: Optional subset of calculated features to compile;
                compiles the full spec document when omitted.
        """
        spec_definition = state.load_spec()
        plan = compiler.Compiler(spec_definition, features=feature_ids).compile()
        return _to_json(
            {
                "features": feature_ids,
                "stages": [
                    [
                        {
                            "id": callable.id,
                            "operation": callable.operation,
                            "function_id": callable.function_id,
                        }
                        for callable in stage
                    ]
                    for stage in plan.execution_stages
                ],
                "callable_count": sum(len(stage) for stage in plan.execution_stages),
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

        spec_definition = state.load_spec()
        plan = compiler.Compiler(spec_definition, features=[feature_id]).compile()
        engine = uptimely_engine.Engine(
            plan,
            config=state.engine_config,
            bind=state.bind,
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
        entity = spec_definition.entities.get(entity_id)
        columns = [
            name
            for name in [*(entity.dimension_ids if entity else []), feature_id]
            if name in frame.columns
        ]
        view = frame.select(columns) if columns else frame
        rows = view.head(max_rows).to_dicts()
        payload: dict[str, typing.Any] = {
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
    def reload_spec() -> str:
        """Re-parse the spec file after editing it or its function entrypoints."""
        spec_definition = state.load_spec(reload=True)
        return _to_json(
            {
                "spec": str(state.spec_path),
                "entities": sorted(spec_definition.entities),
                "functions": {
                    operation: sum(
                        function.operation == operation
                        for function in spec_definition.functions.root.values()
                    )
                    for operation in FUNCTION_OPERATIONS
                },
            }
        )

    return mcp


def _load_engine_config(
    config_path: pathlib.Path | None,
) -> tuple[
    uptimely_engine.EngineConfig,
    dict[str, dict[str, dict[str, typing.Any]]],
]:
    """Load engine settings and runtime bindings from a JSON file."""
    if config_path is None:
        return uptimely_engine.EngineConfig(), {}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Engine configuration JSON must contain an object")
    backend_values = payload.get("backend", {})
    bind = payload.get("bind", {})
    if not isinstance(backend_values, dict):
        raise ValueError("The 'backend' value must be an object")
    if not isinstance(bind, dict):
        raise ValueError("The 'bind' value must be an object")
    return uptimely_engine.EngineConfig(**backend_values), bind


def main() -> None:
    """Launch the uptimely MCP server over stdio."""
    parser = argparse.ArgumentParser(description="Uptimely MCP server")
    parser.add_argument("--spec", required=True, type=pathlib.Path, help="Path to spec JSON")
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Root added to sys.path so function entrypoints are importable",
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=None,
        help="JSON file with engine settings and bind values",
    )
    args = parser.parse_args()

    # Log to stderr only: stdout is the MCP protocol channel.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("Starting uptimely MCP server for spec %s", args.spec)

    engine_config, bind = _load_engine_config(args.config)
    state = ServerState(
        spec_path=args.spec,
        project_root=args.project_root,
        engine_config=engine_config,
        bind=bind,
    )
    create_server(state).run()


if __name__ == "__main__":
    sys.exit(main())
