"""Serve saved-build introspection and execution over MCP.

The server exposes two layers of tools:

* Introspection over the function catalog and calculated features.
* Execution of the saved plan and its dimension-keyed calculated outputs.
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

from uptimely import engine as uptimely_engine
from uptimely import entrypoint, spec
from uptimely.project import build as project_build
from uptimely.spec import model as spec_model
from uptimely.spec import references

logger = logging.getLogger(__name__)

FUNCTION_OPERATIONS = spec_model.FUNCTION_OPERATIONS


@dataclasses.dataclass(frozen=True)
class BuildSnapshot:
    """A validated bundle and its parsed source model from the same read."""

    bundle: project_build.BuildBundle
    spec: spec_model.Spec


@dataclasses.dataclass
class ServerState:
    """Project root, runtime settings, and the currently loaded build snapshot."""

    project_root: pathlib.Path
    engine_config: uptimely_engine.EngineConfig = dataclasses.field(
        default_factory=uptimely_engine.EngineConfig
    )
    bind: dict[str, dict[str, dict[str, typing.Any]]] = dataclasses.field(default_factory=dict)
    snapshot: BuildSnapshot | None = dataclasses.field(default=None, repr=False)

    def load_snapshot(self, *, reload: bool = False) -> BuildSnapshot:
        """Load one consistent validated bundle and parse its saved spec."""
        if self.snapshot is not None and not reload:
            return self.snapshot
        if reload:
            self.snapshot = None

        with project_build.read_build_bundle(self.project_root) as bundle:
            try:
                spec_definition = spec.load_spec(bundle.spec_path)
            except (
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ) as error:
                raise project_build.BuildError(
                    "invalid",
                    f"cannot load saved spec: {error}",
                    self.project_root.resolve(),
                ) from error
            snapshot = BuildSnapshot(bundle=bundle, spec=spec_definition)
        self.snapshot = snapshot
        return snapshot


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


def _build_details(snapshot: BuildSnapshot) -> dict[str, typing.Any]:
    """Describe the saved build scope without implying that it was recompiled."""
    features = snapshot.bundle.manifest.features
    return {
        "uptimely_version": snapshot.bundle.manifest.uptimely_version,
        "scope": "all features" if features is None else "selected features",
        "features": features,
    }


def create_server(state: ServerState) -> fastmcp.FastMCP:
    """Create the MCP server with tools bound to the given server state."""
    project_build.prepare_project_root(state.project_root)

    mcp = fastmcp.FastMCP("uptimely")

    @mcp.tool()
    def list_functions() -> str:
        """List every function id and its operation."""
        catalog = state.load_snapshot().spec.functions
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
        catalog = state.load_snapshot().spec.functions
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
        """List calculated feature ids declared by the saved source model.

        The saved execution scope is reported by ``describe_build``.
        """
        spec_definition = state.load_snapshot().spec
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
        spec_definition = state.load_snapshot().spec
        by_feature = {
            feature: (entity_id, mapping)
            for entity_id, _dataset, mapping in references.iter_mappings(spec_definition)
            if spec_definition.functions[mapping.binding.function].operation == "vectorize"
            for feature in mapping.output_features
        }
        producer = by_feature.get(feature_id)
        if producer is None:
            raise ValueError(
                f"Unknown calculated feature: {feature_id}. "
                "Use list_calculated_features to see available features."
            )

        entity_id, mapping = producer
        transitive: list[str] = []
        queue = list(mapping.input_features)
        seen = set(queue)
        while queue:
            current = queue.pop(0)
            transitive.append(current)
            parent_producer = by_feature.get(current)
            if parent_producer is not None:
                for parent in parent_producer[1].input_features:
                    if parent not in seen:
                        seen.add(parent)
                        queue.append(parent)

        return _to_json(
            {
                "feature": feature_id,
                "entity": entity_id,
                "function": mapping.binding.function,
                "direct_dependencies": mapping.input_features,
                "transitive_dependencies": transitive,
                "input_features": [name for name in transitive if name not in by_feature],
                "calculated_dependencies": [name for name in transitive if name in by_feature],
            }
        )

    @mcp.tool()
    def describe_build() -> str:
        """Report the validated saved build's version and execution scope."""
        return _to_json(_build_details(state.load_snapshot()))

    @mcp.tool()
    def execute_build(max_rows: int = 50) -> str:
        """Execute the saved plan as-is and return dimension-keyed calculated rows.

        Args:
            max_rows: Positive maximum number of rows included per dataset.

        Returns:
            Calculated dataset outputs as JSON rows, or engine failures. The
            saved plan's configured sinks also run and may persist output.
        """
        if max_rows < 1:
            raise ValueError("max_rows must be a positive integer")

        snapshot = state.load_snapshot()
        plan = snapshot.bundle.execution_plan
        engine = uptimely_engine.Engine(
            plan,
            config=state.engine_config,
            bind=state.bind,
        )
        result = engine.execute()

        expected_outputs = {
            (callable.entity_id, callable.dataset_id, feature)
            for callable in plan.callables
            if callable.operation == "vectorize"
            for feature in callable.output_features
        }
        actual_outputs = set(result.calculated_outputs)
        outputs_by_dataset: dict[tuple[str, str], list[str]] = {}
        for entity_id, dataset_id, feature_id in sorted(actual_outputs):
            outputs_by_dataset.setdefault((entity_id, dataset_id), []).append(feature_id)

        datasets: list[dict[str, typing.Any]] = []
        for (entity_id, dataset_id), features in sorted(outputs_by_dataset.items()):
            frame = _collect_frame(result.datasets.get((entity_id, dataset_id)))
            if frame is None or not hasattr(frame, "to_dicts"):
                raise TypeError(
                    f"Execution produced calculated outputs for {entity_id}.{dataset_id} "
                    "without a serializable dataset"
                )
            entity = snapshot.spec.entities.get(entity_id)
            columns = [
                name
                for name in [*(entity.dimension_ids if entity else []), *features]
                if name in frame.columns
            ]
            view = frame.select(columns) if columns else frame
            rows = view.head(max_rows).to_dicts()
            datasets.append(
                {
                    "entity": entity_id,
                    "dataset": dataset_id,
                    "features": features,
                    "columns": view.columns,
                    "row_count": len(rows),
                    "rows": rows,
                }
            )

        outputs_complete = expected_outputs <= actual_outputs
        has_expected_outputs = bool(expected_outputs)
        status = (
            "ok" if outputs_complete and (has_expected_outputs or not result.failures) else "failed"
        )
        payload: dict[str, typing.Any] = {
            "status": status,
            **_build_details(snapshot),
            "datasets": datasets,
        }
        if result.failures:
            payload["warnings" if status == "ok" else "failures"] = result.failures
        return _to_json(payload)

    @mcp.tool()
    def reload_build() -> str:
        """Refresh the validated saved bundle, spec, plan, and recorded scope."""
        snapshot = state.load_snapshot(reload=True)
        spec_definition = snapshot.spec
        return _to_json(
            {
                **_build_details(snapshot),
                "spec": str(snapshot.bundle.spec_path),
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
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Analytics project root containing the last successful build",
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
    logger.info("Starting uptimely MCP server for project %s", args.project_root)

    engine_config, bind = _load_engine_config(args.config)
    state = ServerState(
        project_root=args.project_root,
        engine_config=engine_config,
        bind=bind,
    )
    create_server(state).run()


if __name__ == "__main__":
    sys.exit(main())
