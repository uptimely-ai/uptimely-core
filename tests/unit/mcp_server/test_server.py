"""In-memory client tests for the uptimely MCP server."""

import dataclasses
import json
import pathlib
import shlex
import sys

import pytest
from conftest import EXAMPLES_ROOT

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

import fastmcp as fastmcp_  # noqa: E402

from uptimely import compiler  # noqa: E402
from uptimely.explorer import explorer as explorer_module  # noqa: E402
from uptimely.mcp import server  # noqa: E402
from uptimely.spec import model as spec_model  # noqa: E402

PROJECT_ROOT = EXAMPLES_ROOT / "pump_analytics"
BUILD_MANIFEST_PATH = PROJECT_ROOT / "_generated" / "build" / "build.json"
CONFIG_PATH = EXAMPLES_ROOT / "pump_analytics" / "config" / "engine.json"

pytestmark = pytest.mark.skipif(
    not BUILD_MANIFEST_PATH.exists(), reason="example build is not generated"
)


@pytest.fixture()
def state() -> server.ServerState:
    """Provide server state bound to the pump analytics build."""
    engine_config = server._load_engine_config(CONFIG_PATH)
    return server.ServerState(
        project_root=PROJECT_ROOT,
        engine_config=engine_config,
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
async def test_list_functions_returns_function_kinds(state: server.ServerState) -> None:
    """list_functions returns each function id and declared kind."""
    payload = await _call(state, "list_functions")
    assert {
        "id": "pump_health_score",
        "kind": "vectorize",
        "returns": "dataframe",
    } in payload


@pytest.mark.anyio
async def test_describe_function_resolves_signature(state: server.ServerState) -> None:
    """describe_function returns declared args and the resolved Python signature."""
    payload = await _call(state, "describe_function", {"function_id": "pump_health_score"})
    assert payload["kind"] == "vectorize"
    assert payload["entrypoint"].endswith(":pump_health_score")
    assert payload["declared_args"]["health_features"]["type"] == "array[string]"
    assert payload["python_signature_validation"] == "enabled"
    assert payload["python_signature"]["returns"] == "LazyFrame"
    assert payload["declared_returns"] == "dataframe"


@pytest.mark.anyio
async def test_describe_function_skips_disabled_signature_without_importing_parent(
    state: server.ServerState,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "mcp_signature_validation_fixture"
    package.mkdir()
    marker = tmp_path / "parent_imported"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    (package / "calculation.py").write_text(
        "import uptimely_test_missing_dependency\n"
        "def calculate(dataset, output):\n"
        "    return dataset\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    snapshot = state.load_snapshot()
    definition = snapshot.spec.model_copy(deep=True)
    function = definition.functions["pump_health_score"]
    function.entrypoint = "mcp_signature_validation_fixture.calculation:calculate"
    function.validate_signature = False
    state.snapshot = dataclasses.replace(snapshot, spec=definition)

    described = await _call(state, "describe_function", {"function_id": function.id})

    assert not marker.exists()
    assert described["python_signature_validation"] == "disabled"
    assert described["python_signature"] is None
    assert described["entrypoint"] == function.entrypoint
    assert described["declared_returns"] == "dataframe"
    assert described["declared_args"]["health_features"]["type"] == "array[string]"


@pytest.mark.anyio
async def test_escape_function_description_reports_external_feature_boundary(
    state: server.ServerState,
) -> None:
    snapshot = state.load_snapshot()
    definition = snapshot.spec.model_copy(deep=True)
    definition.functions.root["external_audit"] = spec_model.FunctionTemplate(
        id="external_audit",
        kind="escape",
        returns="any",
        entrypoint="examples.pump_analytics.functions.analytics:maximum",
    )
    dataset = definition.entities["pump_telemetry"].datasets["pump_telemetry_dataset"]
    dataset.features["audit_reference"] = spec_model.Feature(id="audit_reference", type="string")
    dataset.features["audit_status"] = spec_model.Feature(id="audit_status", type="string")
    dataset.actions["external_audit"] = spec_model.Action(
        id="external_audit",
        binding=spec_model.Binding(function="external_audit"),
        features=spec_model.ActionFeatures(
            inputs=["$features.bearing_temperature", "$features.vibration_rms"],
            outputs=["$features.audit_reference", "$features.audit_status"],
        ),
    )
    state.snapshot = dataclasses.replace(snapshot, spec=definition)

    listing = await _call(state, "list_functions")
    described = await _call(state, "describe_function", {"function_id": "external_audit"})

    assert {
        "id": "external_audit",
        "kind": "escape",
        "returns": "any",
    } in listing
    assert described["declared_returns"] == "any"
    assert described["escape_actions"] == [
        {
            "entity": "pump_telemetry",
            "dataset": dataset.id,
            "action": "external_audit",
            "inputs": ["bearing_temperature", "vibration_rms"],
            "outputs": ["audit_reference", "audit_status"],
        }
    ]
    assert "return value is ignored" in described["execution_semantics"]


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
