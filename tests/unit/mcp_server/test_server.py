"""In-memory client tests for the uptimely MCP server."""

import json
import pathlib

import pytest

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

import fastmcp as fastmcp_  # noqa: E402

from uptimely.mcp import server  # noqa: E402

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]
ANALYTICS_PATH = (
    REPOSITORY_ROOT / "examples" / "pump_analytics" / "_generated" / "analytics" / "analytics.json"
)
CONFIG_PATH = REPOSITORY_ROOT / "examples" / "pump_analytics" / "config" / "engine.json"

pytestmark = pytest.mark.skipif(
    not ANALYTICS_PATH.exists(), reason="example analytics is not generated"
)


@pytest.fixture()
def state() -> server.ServerState:
    """Provide server state bound to the pump analytics document."""
    engine_config, bind = server._load_engine_config(CONFIG_PATH)
    return server.ServerState(
        analytics_path=ANALYTICS_PATH,
        project_root=REPOSITORY_ROOT,
        engine_config=engine_config,
        bind=bind,
    )


async def _call(state: server.ServerState, tool: str, arguments: dict | None = None) -> dict:
    """Call one tool over the in-memory transport and decode its JSON payload."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        result = await client.call_tool(tool, arguments or {})
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_lists_all_tools(state: server.ServerState) -> None:
    """The server exposes the expected tool names."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        tools = {tool.name for tool in await client.list_tools()}
    assert {
        "list_functions",
        "describe_function",
        "list_calculated_features",
        "describe_feature",
        "compile_plan",
        "execute_feature",
        "reload_analytics",
    } <= tools


@pytest.mark.anyio
async def test_list_functions_returns_function_operations(state: server.ServerState) -> None:
    """list_functions returns each function id and declared operation."""
    payload = await _call(state, "list_functions")
    assert {"id": "pump_health_score", "operation": "vectorize"} in payload


@pytest.mark.anyio
async def test_describe_function_resolves_signature(state: server.ServerState) -> None:
    """describe_function returns declared args and the resolved Python signature."""
    payload = await _call(state, "describe_function", {"function_id": "pump_health_score"})
    assert payload["operation"] == "vectorize"
    assert payload["entrypoint"].endswith(":pump_health_score")
    assert payload["declared_args"]["health_features"]["type"] == "array[string]"
    assert payload["python_signature"]["returns"] == "LazyFrame"


@pytest.mark.anyio
async def test_describe_function_rejects_unknown_ids(
    state: server.ServerState,
) -> None:
    """describe_function fails with a clear error for unknown functions."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown function"):
            await client.call_tool("describe_function", {"function_id": "nope"})


@pytest.mark.anyio
async def test_list_calculated_features(state: server.ServerState) -> None:
    """list_calculated_features returns sorted calculated feature ids."""
    payload = await _call(state, "list_calculated_features")
    assert payload == [
        "bearing_temperature_delta",
        "converged",
        "energy_cost_score",
        "health_signal_normalized",
        "operating_point_recommendation",
        "pressure_flow_efficiency",
        "pump_health_score",
        "recommended_discharge_pressure",
        "recommended_flow_rate",
        "vibration_delta",
    ]


@pytest.mark.anyio
async def test_describe_feature_reports_dependencies(
    state: server.ServerState,
) -> None:
    """describe_feature reports direct, transitive, and input dependencies."""
    payload = await _call(state, "describe_feature", {"feature_id": "pump_health_score"})
    assert payload["function"] == "pump_health_score"
    assert payload["entity"] == "pump_telemetry"
    assert payload["direct_dependencies"] == [
        "bearing_temperature_delta",
        "vibration_delta",
        "pressure_flow_efficiency",
    ]
    assert "bearing_temperature" in payload["input_features"]
    assert "bearing_temperature" in payload["transitive_dependencies"]
    assert "pressure_flow_efficiency" in payload["calculated_dependencies"]


@pytest.mark.anyio
async def test_describe_feature_rejects_unknown_feature(
    state: server.ServerState,
) -> None:
    """describe_feature fails with a clear error for unknown features."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown calculated feature"):
            await client.call_tool("describe_feature", {"feature_id": "nope"})


@pytest.mark.anyio
async def test_compile_plan_subset(state: server.ServerState) -> None:
    """compile_plan compiles a feature subset into staged callables."""
    payload = await _call(state, "compile_plan", {"feature_ids": ["pump_health_score"]})
    assert payload["callable_count"] > 0
    operations = {callable["operation"] for stage in payload["stages"] for callable in stage}
    assert "read" in operations
    assert "vectorize" in operations


@pytest.mark.anyio
async def test_compile_plan_empty_subset_is_empty(state: server.ServerState) -> None:
    """An explicit empty feature subset does not compile the full analytics document."""
    payload = await _call(state, "compile_plan", {"feature_ids": []})
    assert payload["features"] == []
    assert payload["stages"] == []
    assert payload["callable_count"] == 0


@pytest.mark.anyio
async def test_execute_feature_returns_rows(state: server.ServerState) -> None:
    """execute_feature returns dimension-keyed rows for a calculated feature."""
    payload = await _call(
        state, "execute_feature", {"feature_id": "pump_health_score", "max_rows": 3}
    )
    assert payload["status"] == "ok"
    assert payload["entity"] == "pump_telemetry"
    assert payload["columns"] == [
        "plant",
        "production_line",
        "pump",
        "timestamp",
        "pump_health_score",
    ]
    assert payload["row_count"] == 3
    assert {"plant", "pump", "pump_health_score"} <= set(payload["rows"][0])


@pytest.mark.anyio
async def test_execute_feature_rejects_nonpositive_row_limit(
    state: server.ServerState,
) -> None:
    """execute_feature rejects limits that cannot produce a useful row response."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="max_rows must be a positive integer"):
            await client.call_tool(
                "execute_feature", {"feature_id": "pump_health_score", "max_rows": 0}
            )


@pytest.mark.anyio
async def test_reload_analytics(state: server.ServerState) -> None:
    """reload_analytics re-parses the analytics file and reports its contents."""
    payload = await _call(state, "reload_analytics")
    assert payload["entities"] == ["pump", "pump_telemetry"]
