import json
import pathlib

import fastmcp as fastmcp_
import pytest
from support import examples as example_support

from uptimely import application
from uptimely.mcp import server
from uptimely.mcp import state as mcp_state

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
async def test_targeted_execution_reports_not_supported(state: mcp_state.ServerState) -> None:
    operator_id = _operator_id_for_output(state, "pump_telemetry", "pump_health_score")
    requests = [
        (
            "execute_operator",
            {"profile_id": "pump_telemetry", "operator_id": operator_id},
        ),
        ("execute_function", {"function_id": "pump_health_score"}),
    ]
    async with fastmcp_.Client(server.create_server(state)) as client:
        for tool, arguments in requests:
            with pytest.raises(Exception, match="Targeted execution is not yet supported"):
                await client.call_tool(tool, arguments)


@pytest.mark.anyio
async def test_execute_function_requires_unambiguous_usage(
    state: mcp_state.ServerState,
) -> None:
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Ambiguous function"):
            await client.call_tool("execute_function", {"function_id": "aggregate"})

    definition = state.load_bundle().spec_definition
    profile_id, operator_id = definition.operators_by_function["aggregate"][0]
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Targeted execution is not yet supported"):
            await client.call_tool(
                "execute_function",
                {
                    "function_id": "aggregate",
                    "profile_id": profile_id,
                    "operator_id": operator_id,
                    "max_rows": 1,
                },
            )


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
async def test_last_run_tools_read_external_execution_without_current_build(
    state: mcp_state.ServerState, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = state.load_bundle()
    runtime = state.app.create_engine(bundle)
    runtime.run(preview_rows=1)
    monkeypatch.setattr(
        state, "load_bundle", lambda **kwargs: pytest.fail("Run tools must not load the build")
    )

    manifest = await _call(state, "describe_last_run")
    logs = await _call(state, "read_last_run_logs", {"run_id": manifest["run_id"]})

    assert manifest["status"] == "succeeded"
    assert logs["run_id"] == manifest["run_id"]
    assert logs["next_offset"] == len(logs["entries"])


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["describe_last_run", "read_last_run_logs"])
async def test_last_run_tools_report_missing_runs(tmp_path: pathlib.Path, tool: str) -> None:
    state = mcp_state.ServerState(application.Uptimely(tmp_path))
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="No saved run"):
            await client.call_tool(tool)


@pytest.mark.anyio
async def test_last_run_logs_reject_stale_run_id(state: mcp_state.ServerState) -> None:
    await _call(state, "execute_build", {"max_rows": 1})
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="latest run changed"):
            await client.call_tool("read_last_run_logs", {"run_id": "old-run"})
