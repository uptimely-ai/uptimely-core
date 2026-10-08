"""In-memory client tests for the uptimely MCP server."""

import json
from pathlib import Path

import pytest

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

from fastmcp import Client  # noqa: E402

from uptimely.mcp.server import ServerState, create_server  # noqa: E402

REPOSITORY_ROOT = Path(__file__).parents[3]
SPEC_PATH = REPOSITORY_ROOT / "examples" / "example_1" / "generated" / "spec" / "spec.json"
RUNTIME_RESOURCES_PATH = REPOSITORY_ROOT / "examples" / "example_1" / "runtime-resources.json"

pytestmark = pytest.mark.skipif(not SPEC_PATH.exists(), reason="example spec is not generated")


@pytest.fixture()
def state() -> ServerState:
    """Provide server state bound to the example 1 specification."""
    return ServerState(
        spec_path=SPEC_PATH,
        project_root=REPOSITORY_ROOT,
        runtime_resources=json.loads(RUNTIME_RESOURCES_PATH.read_text(encoding="utf-8")),
    )


async def _call(state: ServerState, tool: str, arguments: dict | None = None) -> dict:
    """Call one tool over the in-memory transport and decode its JSON payload."""
    async with Client(create_server(state)) as client:
        result = await client.call_tool(tool, arguments or {})
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_lists_all_tools(state: ServerState) -> None:
    """The server exposes the expected tool names."""
    async with Client(create_server(state)) as client:
        tools = {tool.name for tool in await client.list_tools()}
    assert {
        "list_functions",
        "describe_function",
        "list_calculated_features",
        "describe_feature",
        "compile_plan",
        "execute_feature",
        "reload_specification",
    } <= tools


@pytest.mark.anyio
async def test_list_functions_groups_catalog(state: ServerState) -> None:
    """list_functions groups function ids by category."""
    payload = await _call(state, "list_functions")
    assert "pump_health_score" in payload["vectorize"]
    assert sorted(payload) == sorted(
        ["read", "write", "vectorize", "aggregate", "collapse", "expand", "conform"]
    )


@pytest.mark.anyio
async def test_describe_function_resolves_signature(state: ServerState) -> None:
    """describe_function returns declared args and the resolved Python signature."""
    payload = await _call(
        state, "describe_function", {"category": "vectorize", "function_id": "pump_health_score"}
    )
    assert payload["entrypoint"].endswith(":pump_health_score")
    assert payload["declared_args"]["health_features"]["type"] == "array[string]"
    assert payload["python_signature"]["returns"] == "Expr"


@pytest.mark.anyio
async def test_describe_function_rejects_unknown_ids(state: ServerState) -> None:
    """describe_function fails with a clear error for unknown categories or functions."""
    async with Client(create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown category"):
            await client.call_tool(
                "describe_function", {"category": "nope", "function_id": "pump_health_score"}
            )
        with pytest.raises(Exception, match="Unknown vectorize function"):
            await client.call_tool(
                "describe_function", {"category": "vectorize", "function_id": "nope"}
            )


@pytest.mark.anyio
async def test_list_calculated_features(state: ServerState) -> None:
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
async def test_describe_feature_reports_dependencies(state: ServerState) -> None:
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
async def test_describe_feature_rejects_unknown_feature(state: ServerState) -> None:
    """describe_feature fails with a clear error for unknown features."""
    async with Client(create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown calculated feature"):
            await client.call_tool("describe_feature", {"feature_id": "nope"})


@pytest.mark.anyio
async def test_compile_plan_subset(state: ServerState) -> None:
    """compile_plan compiles a feature subset into staged operations."""
    payload = await _call(state, "compile_plan", {"feature_ids": ["pump_health_score"]})
    assert payload["operation_count"] > 0
    kinds = {operation["kind"] for stage in payload["stages"] for operation in stage}
    assert "read" in kinds
    assert "vectorize" in kinds


@pytest.mark.anyio
async def test_compile_plan_empty_subset_is_empty(state: ServerState) -> None:
    """An explicit empty feature subset does not compile the full specification."""
    payload = await _call(state, "compile_plan", {"feature_ids": []})
    assert payload["features"] == []
    assert payload["stages"] == []
    assert payload["operation_count"] == 0


@pytest.mark.anyio
async def test_execute_feature_returns_rows(state: ServerState) -> None:
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
async def test_execute_feature_rejects_nonpositive_row_limit(state: ServerState) -> None:
    """execute_feature rejects limits that cannot produce a useful row response."""
    async with Client(create_server(state)) as client:
        with pytest.raises(Exception, match="max_rows must be a positive integer"):
            await client.call_tool(
                "execute_feature", {"feature_id": "pump_health_score", "max_rows": 0}
            )


@pytest.mark.anyio
async def test_reload_specification(state: ServerState) -> None:
    """reload_specification re-parses the spec and reports its contents."""
    payload = await _call(state, "reload_specification")
    assert payload["entities"] == ["pump", "pump_telemetry"]
