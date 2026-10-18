"""In-memory client tests for the uptimely MCP server."""

import json
import pathlib
import shlex
import sys

import pytest

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

import fastmcp as fastmcp_  # noqa: E402

from uptimely import compiler  # noqa: E402
from uptimely.explorer import explorer as explorer_module  # noqa: E402
from uptimely.mcp import server  # noqa: E402

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]
PROJECT_ROOT = REPOSITORY_ROOT / "examples" / "pump_analytics"
BUILD_MANIFEST_PATH = PROJECT_ROOT / "_generated" / "build" / "build.json"
CONFIG_PATH = REPOSITORY_ROOT / "examples" / "pump_analytics" / "config" / "engine.json"

pytestmark = pytest.mark.skipif(
    not BUILD_MANIFEST_PATH.exists(), reason="example build is not generated"
)


@pytest.fixture()
def state() -> server.ServerState:
    """Provide server state bound to the pump analytics build."""
    engine_config, bind = server._load_engine_config(CONFIG_PATH)
    return server.ServerState(
        project_root=PROJECT_ROOT,
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
        "describe_build",
        "execute_build",
        "reload_build",
    } <= tools
    assert not {"compile_plan", "execute_feature", "reload_spec"} & tools


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
async def test_describe_build_reports_saved_scope(state: server.ServerState) -> None:
    """describe_build reports the scope declared by the validated bundle."""
    payload = await _call(state, "describe_build")
    assert payload["scope"] == "all features"
    assert payload["features"] is None
    assert payload["uptimely_version"]


@pytest.mark.anyio
async def test_execute_build_runs_the_saved_plan_without_compile_or_render(
    state: server.ServerState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """execute_build runs saved outputs and does not compile or render a new build."""
    monkeypatch.setattr(
        compiler.Compiler,
        "compile",
        lambda *_args, **_kwargs: pytest.fail("MCP must not compile plans"),
    )
    monkeypatch.setattr(
        explorer_module.Explorer,
        "create_html",
        lambda *_args, **_kwargs: pytest.fail("MCP must not render Explorer"),
    )

    payload = await _call(state, "execute_build", {"max_rows": 3})
    assert payload["status"] == "ok"
    assert payload["features"] is None
    telemetry = next(
        dataset for dataset in payload["datasets"] if "pump_health_score" in dataset["features"]
    )
    assert telemetry["entity"] == "pump_telemetry"
    assert telemetry["row_count"] == 3
    assert {
        "plant",
        "production_line",
        "pump",
        "timestamp",
        "pump_health_score",
    } <= set(telemetry["columns"])
    assert {"plant", "pump", "pump_health_score"} <= set(telemetry["rows"][0])
    assert (await _call(state, "reload_build"))["features"] is None


@pytest.mark.anyio
async def test_execute_build_rejects_nonpositive_row_limit(
    state: server.ServerState,
) -> None:
    """execute_build rejects limits that cannot produce a useful row response."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="max_rows must be a positive integer"):
            await client.call_tool("execute_build", {"max_rows": 0})


@pytest.mark.anyio
async def test_reload_build(state: server.ServerState) -> None:
    """reload_build refreshes the bundle, source model, and recorded scope."""
    payload = await _call(state, "reload_build")
    assert payload["scope"] == "all features"
    assert payload["features"] is None
    assert payload["spec"].endswith("_generated/build/spec.json")
    assert payload["entities"] == ["pump", "pump_telemetry"]


@pytest.mark.anyio
async def test_missing_build_fails_with_recovery_command(tmp_path: pathlib.Path) -> None:
    """MCP reports missing saved builds explicitly instead of loading source files."""
    project_root = tmp_path / "missing project"
    state = server.ServerState(project_root=project_root)

    with pytest.raises(Exception, match="uptimely project build") as error:
        await _call(state, "list_functions")

    assert shlex.quote(str(project_root.resolve())) in str(error.value)


def test_mcp_cli_rejects_spec_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP process accepts project builds, not standalone spec paths."""
    monkeypatch.setattr(sys, "argv", ["uptimely-mcp", "--spec", "spec.json"])

    with pytest.raises(SystemExit) as error:
        server.main()

    assert error.value.code == 2
