import dataclasses
import json
import logging
import pathlib

import fastmcp as fastmcp_
import pump_io as io
import pytest
from support import examples as example_support

from uptimely import application, compiler, engine
from uptimely import plan as plan_module
from uptimely.mcp import server
from uptimely.mcp import state as mcp_state
from uptimely.project import paths
from uptimely.run import store as run_store

CONFIG_PATH = example_support.EXAMPLES_ROOT / "uptimely.toml"


@pytest.fixture()
def state(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> mcp_state.ServerState:
    """Provide server state bound to the pump analytics build."""
    root = example_project_factory(tmp_path / "project")
    return mcp_state.ServerState(application.Uptimely(root, config_path=CONFIG_PATH))


async def _call(state: mcp_state.ServerState, tool: str, arguments: dict | None = None) -> dict:
    """Call one tool over the in-memory transport and decode its JSON payload."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        result = await client.call_tool(tool, arguments or {})
    return json.loads(result.content[0].text)


def _operator_id_for_output(state: mcp_state.ServerState, profile_id: str, feature_id: str) -> str:
    profile = state.load_bundle().spec_definition.profiles[profile_id]
    return example_support.operator_id_for_output(profile.assembly, feature_id)


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["execute_operator", "execute_function"])
async def test_targeted_execution_returns_only_requested_outputs(
    state: mcp_state.ServerState, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    monkeypatch.setattr(
        compiler.Compiler,
        "compile",
        lambda *_args, **_kwargs: pytest.fail("MCP must not compile plans"),
    )
    bundle = state.load_bundle()
    operator_id = example_support.operator_id_for_output(
        bundle.spec_definition.profiles["pump_telemetry"].assembly, "pump_health_score"
    )
    arguments = (
        {"profile_id": "pump_telemetry", "operator_id": operator_id}
        if tool == "execute_operator"
        else {"function_id": "pump_health_score"}
    )

    payload = await _call(state, tool, {**arguments, "max_rows": 2})

    assert payload["status"] == "ok"
    assert payload["target"] == {"profile": "pump_telemetry", "operator": operator_id}
    assert len(payload["datasets"]) == 1
    dataset = payload["datasets"][0]
    assert dataset["features"] == ["pump_health_score"]
    assert dataset["row_count"] == 2
    assert set(dataset["columns"]) == {
        *bundle.spec_definition.identifiers_by_profile["pump_telemetry"],
        "pump_health_score",
    }
    saved = run_store.RunStore(state.project_root).read_manifest()
    selected = bundle.execution_plan.for_operator("pump_telemetry", operator_id)
    assert {
        invocation_id
        for invocation_id, outcome in saved.invocations.items()
        if outcome.status == "succeeded"
    } == set(selected.invocations_by_id)
    assert all(
        saved.invocations[invocation.id].status == "skipped"
        for invocation in bundle.execution_plan.invocations
        if invocation.is_sink
    )
    assert saved.preview_rows == 2
    assert len(run_store.RunStore(state.project_root).read_preview("pump_telemetry").rows) == 2


@pytest.mark.anyio
async def test_execute_function_requires_unambiguous_usage(
    state: mcp_state.ServerState,
) -> None:
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Ambiguous function"):
            await client.call_tool("execute_function", {"function_id": "aggregate"})

    definition = state.load_bundle().spec_definition
    profile_id, operator_id = definition.operators_by_function["aggregate"][0]
    payload = await _call(
        state,
        "execute_function",
        {
            "function_id": "aggregate",
            "profile_id": profile_id,
            "operator_id": operator_id,
            "max_rows": 1,
        },
    )

    assert payload["status"] == "ok"
    assert payload["target"] == {"profile": profile_id, "operator": operator_id}
    assert payload["datasets"][0]["row_count"] == 1


@pytest.mark.anyio
async def test_targeted_optimization_returns_structured_numerical_results(
    state: mcp_state.ServerState,
) -> None:
    payload = await _call(
        state,
        "execute_function",
        {"function_id": "operation_point_optimization", "max_rows": 1},
    )

    assert payload["status"] == "ok"
    assert payload["datasets"][0]["features"] == ["operating_point_recommendation"]
    row = payload["datasets"][0]["rows"][0]
    assert row["pump_id"] == "CWP-301"
    assert row["hour"] == "2026-09-01T08:00:00+00:00"
    assert row["operating_point_recommendation"] == {
        "recommended_flow_rate": 182.0,
        "recommended_differential_pressure": 6.6,
        "energy_cost_score": pytest.approx(30.0 / 182.0),
        "converged": False,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("execute_function", {"function_id": "unknown"}, "Unknown function"),
        (
            "execute_function",
            {"function_id": "pump_health_score", "profile_id": "unknown"},
            "No matching operator usage",
        ),
        (
            "execute_operator",
            {"profile_id": "pump_telemetry", "operator_id": "unknown"},
            "Unknown operator",
        ),
        (
            "execute_operator",
            {"profile_id": "pump_telemetry", "operator_id": "pump_health_score", "max_rows": 0},
            "max_rows must be a positive integer",
        ),
    ],
)
async def test_targeted_execution_rejects_invalid_requests(
    state: mcp_state.ServerState, tool: str, arguments: dict[str, object], message: str
) -> None:
    if tool == "execute_operator" and arguments.get("operator_id") == "pump_health_score":
        arguments = {
            **arguments,
            "operator_id": _operator_id_for_output(state, "pump_telemetry", "pump_health_score"),
        }
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match=message):
            await client.call_tool(tool, arguments)


@pytest.mark.anyio
async def test_targeted_execution_rejects_operators_outside_saved_scope(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> None:
    root = example_project_factory(tmp_path / "scoped", features=("pressure_flow_efficiency",))
    state = mcp_state.ServerState(application.Uptimely(root))
    listing = await _call(state, "list_operators")
    assert not next(
        item
        for item in listing
        if item["bindings"].get("compute") == "process_pump_external_workflow"
    )["in_saved_scope"]
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="not in the saved execution scope"):
            await client.call_tool(
                "execute_function", {"function_id": "process_pump_external_workflow"}
            )

    assert not (root / paths.RUN_OUTPUT_DIR).exists()


@pytest.mark.anyio
async def test_last_run_tools_read_external_execution_without_current_build(
    state: mcp_state.ServerState, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = state.load_bundle()
    runtime = state.app.create_engine(bundle)
    original_execute = runtime._execute

    def execute(
        *, validate: bool, plan: plan_module.ExecutionPlan | None = None
    ) -> engine.ExecutionResult:
        logging.getLogger(__name__).warning("Source observations are delayed")
        return original_execute(validate=validate, plan=plan)

    monkeypatch.setattr(runtime, "_execute", execute)
    operator_id = example_support.operator_id_for_output(
        bundle.spec_definition.profiles["pump_telemetry"].assembly, "pressure_flow_efficiency"
    )
    runtime.run(operator=("pump_telemetry", operator_id), preview_rows=1)
    monkeypatch.setattr(
        state, "load_bundle", lambda **kwargs: pytest.fail("Run tools must not load the build")
    )

    manifest = await _call(state, "describe_last_run")
    logs = await _call(
        state, "read_last_run_logs", {"level": "WARNING", "run_id": manifest["run_id"]}
    )

    assert manifest["status"] == "succeeded"
    assert logs["run_id"] == manifest["run_id"]
    assert [entry["message"] for entry in logs["entries"]] == ["Source observations are delayed"]
    assert logs["next_offset"] == 1
    assert (await _call(state, "read_last_run_logs", {"level": "WARNING", "offset": 1}))[
        "entries"
    ] == []


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["describe_last_run", "read_last_run_logs"])
async def test_last_run_tools_report_missing_runs(tmp_path: pathlib.Path, tool: str) -> None:
    state = mcp_state.ServerState(application.Uptimely(tmp_path))
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="No saved run"):
            await client.call_tool(tool)


@pytest.mark.anyio
async def test_last_run_logs_reject_stale_run_id(state: mcp_state.ServerState) -> None:
    await _call(state, "execute_function", {"function_id": "pump_health_score", "max_rows": 1})
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="latest run changed"):
            await client.call_tool("read_last_run_logs", {"run_id": "old-run"})


@pytest.mark.anyio
async def test_targeted_execution_reports_failed_previews(
    state: mcp_state.ServerState, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_run = engine.Engine.run

    def run(
        runtime: engine.Engine,
        *,
        operator: tuple[str, str] | None = None,
        preview_rows: int = 50,
        validate: bool = False,
    ) -> engine.ExecutionResult:
        result = original_run(
            runtime, operator=operator, preview_rows=preview_rows, validate=validate
        )
        return dataclasses.replace(
            result,
            preview_frames={},
            preview_failures={"pump_telemetry": "Cannot collect output"},
        )

    monkeypatch.setattr(engine.Engine, "run", run)
    payload = await _call(state, "execute_function", {"function_id": "pump_health_score"})

    assert payload["status"] == "failed"
    assert payload["datasets"] == []
    assert payload["preview_failures"] == {"pump_telemetry": "Cannot collect output"}


@pytest.mark.anyio
async def test_targeted_execution_does_not_fabricate_side_effect_only_results(
    state: mcp_state.ServerState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(io, "process_pump_external_workflow", lambda **_: None)

    payload = await _call(
        state, "execute_function", {"function_id": "process_pump_external_workflow", "max_rows": 1}
    )

    assert payload["status"] == "ok"
    assert "output_failures" not in payload
