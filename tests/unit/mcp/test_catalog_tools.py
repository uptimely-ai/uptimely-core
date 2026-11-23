import dataclasses
import json
import pathlib
import shlex
import sys

import fastmcp as fastmcp_
import pytest
from support import examples as example_support

from uptimely import application, compiler
from uptimely.mcp import server
from uptimely.mcp import state as mcp_state
from uptimely.project import paths
from uptimely.spec import model as spec_model

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


def test_load_config_defaults_to_project_config(tmp_path: pathlib.Path) -> None:
    (tmp_path / paths.CONFIG_FILE).write_text(
        '[engine.backend]\ndataframe = "polars"\n\n[params]\nthreshold = 10\n',
        encoding="utf-8",
    )

    config = application.Uptimely(tmp_path).config

    assert config.engine.backend.dataframe == "polars"
    assert config.params.root == {"threshold": 10}


@pytest.mark.anyio
async def test_lists_all_tools(state: mcp_state.ServerState) -> None:
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
        "describe_spec",
        "list_operators",
        "execute_operator",
        "execute_function",
        "describe_last_run",
        "read_last_run_logs",
    } <= tools
    assert not {"compile_plan", "execute_feature", "reload_spec"} & tools


@pytest.mark.anyio
async def test_list_functions_returns_callable_contracts(state: mcp_state.ServerState) -> None:
    """list_functions returns each function id, category, and return contract."""
    payload = await _call(state, "list_functions")
    assert {
        "id": "pump_health_score",
        "category": "calculate",
        "returns": "dataframe",
    } in payload


@pytest.mark.anyio
async def test_describe_function_resolves_signature(state: mcp_state.ServerState) -> None:
    """describe_function returns declared args and the resolved Python signature."""
    operator_id = _operator_id_for_output(state, "pump_telemetry", "pump_health_score")
    payload = await _call(state, "describe_function", {"function_id": "pump_health_score"})
    assert payload["category"] == "calculate"
    assert payload["entrypoint"].endswith(":pump_health_score")
    assert payload["declared_args"]["health_features"]["type"] == "array[string]"
    assert payload["python_signature_validation"] == "enabled"
    assert payload["python_signature"]["returns"] == "LazyFrame"
    assert payload["declared_returns"] == "dataframe"
    usage = {
        key: value
        for key, value in payload["operator_usages"][0].items()
        if key != "grain_relationships"
    }
    assert usage == {
        "profile": "pump_telemetry",
        "operator": operator_id,
        "role": "compute",
        "execution_form": "compute",
    }


@pytest.mark.anyio
async def test_describe_function_skips_disabled_signature_without_importing_parent(
    state: mcp_state.ServerState,
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

    bundle = state.load_bundle()
    definition = bundle.spec_definition.model_copy(deep=True)
    function = definition.functions["pump_health_score"]
    function.entrypoint = "mcp_signature_validation_fixture.calculation:calculate"
    function.validate_signature = False
    state.bundle = dataclasses.replace(bundle, spec_definition=definition)

    described = await _call(state, "describe_function", {"function_id": function.id})

    assert not marker.exists()
    assert described["python_signature_validation"] == "disabled"
    assert described["python_signature"] is None
    assert described["entrypoint"] == function.entrypoint
    assert described["declared_returns"] == "dataframe"
    assert described["declared_args"]["health_features"]["type"] == "array[string]"


@pytest.mark.anyio
async def test_describe_function_reports_bindings_and_derived_operator_usage(
    state: mcp_state.ServerState,
) -> None:
    bundle = state.load_bundle()
    definition = bundle.spec_definition.model_copy(deep=True)
    definition.functions.root["external_audit"] = spec_model.FunctionTemplate(
        id="external_audit",
        returns="any",
        entrypoint="pump_analytics:aggregate",
    )
    profile = definition.profiles["pump_telemetry"]
    profile.assembly["external_audit"] = spec_model.Operator(
        id="external_audit",
        compute=spec_model.Binding(function="external_audit"),
        interface=spec_model.Interface(
            inputs=["$features.bearing_temperature", "$features.vibration_rms"],
            outputs=[],
        ),
    )
    state.bundle = dataclasses.replace(
        bundle, spec_definition=spec_model.Spec.model_validate(definition.model_dump())
    )

    listing = await _call(state, "list_functions")
    described = await _call(state, "describe_function", {"function_id": "external_audit"})

    assert {
        "id": "external_audit",
        "category": None,
        "returns": "any",
    } in listing
    assert described["declared_returns"] == "any"
    assert described["operator_usages"] == [
        {
            "profile": "pump_telemetry",
            "operator": "external_audit",
            "role": "compute",
            "execution_form": "compute",
            "grain_relationships": [{"source_profile": "pump_telemetry", "relationship": "vanish"}],
        }
    ]


@pytest.mark.anyio
async def test_describe_function_rejects_unknown_ids(
    state: mcp_state.ServerState,
) -> None:
    """describe_function fails with a clear error for unknown functions."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown function"):
            await client.call_tool("describe_function", {"function_id": "nope"})


@pytest.mark.anyio
async def test_list_calculated_features(state: mcp_state.ServerState) -> None:
    """list_calculated_features returns sorted calculated feature ids."""
    payload = await _call(state, "list_calculated_features")
    assert payload == [
        "bearing_temperature_delta",
        "bearing_temperature_rise",
        "converged",
        "energy_cost_score",
        "health_signal_normalized",
        "max_capacity",
        "operating_point_recommendation",
        "pressure_flow_efficiency",
        "pump_health_score",
        "pump_mode",
        "recommended_differential_pressure",
        "recommended_flow_rate",
        "vibration_delta",
    ]


@pytest.mark.anyio
async def test_describe_feature_reports_dependencies(
    state: mcp_state.ServerState,
) -> None:
    """describe_feature reports direct, transitive, and input dependencies."""
    payload = await _call(state, "describe_feature", {"feature_id": "pump_health_score"})
    assert payload["function"] == "pump_health_score"
    assert payload["profile"] == "pump_telemetry"
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
    state: mcp_state.ServerState,
) -> None:
    """describe_feature fails with a clear error for unknown features."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="Unknown calculated feature"):
            await client.call_tool("describe_feature", {"feature_id": "nope"})


@pytest.mark.anyio
async def test_describe_build_reports_saved_scope(state: mcp_state.ServerState) -> None:
    """describe_build reports the scope declared by the validated bundle."""
    payload = await _call(state, "describe_build")
    assert payload["scope"] == "all features"
    assert payload["features"] is None
    assert payload["uptimely_version"]


@pytest.mark.anyio
async def test_execute_build_runs_the_saved_plan_without_compiling(
    state: mcp_state.ServerState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """execute_build runs saved outputs and does not compile a new build."""
    monkeypatch.setattr(
        compiler.Compiler,
        "compile",
        lambda *_args, **_kwargs: pytest.fail("MCP must not compile plans"),
    )
    payload = await _call(state, "execute_build", {"max_rows": 3})
    assert payload["status"] == "ok"
    assert payload["features"] is None
    assert payload["datasets"] == []
    assert payload["output_summary_available"] is False
    assert (await _call(state, "reload_build"))["features"] is None


@pytest.mark.anyio
async def test_execute_build_rejects_nonpositive_row_limit(
    state: mcp_state.ServerState,
) -> None:
    """execute_build rejects limits that cannot produce a useful row response."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match="max_rows must be a positive integer"):
            await client.call_tool("execute_build", {"max_rows": 0})


@pytest.mark.anyio
async def test_reload_build(state: mcp_state.ServerState) -> None:
    """reload_build refreshes the bundle, source model, and recorded scope."""
    payload = await _call(state, "reload_build")
    assert payload["scope"] == "all features"
    assert payload["features"] is None
    assert payload["spec"].endswith("artifacts/build/spec.json")
    assert payload["profiles"] == [
        "constants",
        "pump",
        "pump_category",
        "pump_series",
        "pump_telemetry",
        "pump_telemetry_by_day",
        "pump_telemetry_by_hour",
        "pump_telemetry_by_hour_when_warning",
        "pump_telemetry_by_minute",
        "pump_telemetry_when_warning",
    ]


@pytest.mark.anyio
async def test_missing_build_fails_with_recovery_command(tmp_path: pathlib.Path) -> None:
    """MCP reports missing saved builds explicitly instead of loading source files."""
    project_root = tmp_path / "missing project"
    state = mcp_state.ServerState(application.Uptimely(project_root))

    with pytest.raises(Exception, match="uptimely build") as error:
        await _call(state, "list_functions")

    assert shlex.quote(str(project_root.resolve())) in str(error.value)


def test_mcp_cli_rejects_spec_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP process accepts project builds, not standalone spec paths."""
    monkeypatch.setattr(sys, "argv", ["uptimely-mcp", "--spec", "spec.json"])

    with pytest.raises(SystemExit) as error:
        server.main()

    assert error.value.code == 2


def test_bundle_caches_validated_spec(state: mcp_state.ServerState) -> None:
    bundle = state.load_bundle()
    assert state.load_bundle() is bundle
    assert state.load_bundle(reload=True) is not bundle


@pytest.mark.anyio
async def test_describe_spec_counts_all_declarations(state: mcp_state.ServerState) -> None:
    definition = state.load_bundle().spec_definition

    payload = await _call(state, "describe_spec")

    assert payload["features"] == sum(
        len(profile.features) for profile in definition.profiles.values()
    )
    assert payload["calculated_features"] == len(definition.calculated_feature_producers)
    assert payload["functions"] == len(definition.functions.root)
    assert payload["operators"] == len(definition.operators)
    assert payload["dimensions"] == len(definition.dimensions)
    assert payload["profiles"]["pump_telemetry"]["features"] == len(
        definition.profiles["pump_telemetry"].features
    )


@pytest.mark.anyio
async def test_list_operators_reports_bindings_and_scope(state: mcp_state.ServerState) -> None:
    payload = await _call(state, "list_operators")
    operator_id = _operator_id_for_output(state, "pump_telemetry", "pump_health_score")
    operator = next(
        item
        for item in payload
        if item["profile"] == "pump_telemetry" and item["output_features"] == ["pump_health_score"]
    )

    assert operator == {
        "profile": "pump_telemetry",
        "operator": operator_id,
        "bindings": {"compute": "pump_health_score"},
        "input_features": [
            "bearing_temperature_delta",
            "vibration_delta",
            "pressure_flow_efficiency",
        ],
        "output_features": ["pump_health_score"],
        "execution_form": "compute",
        "declared_returns": "dataframe",
        "in_saved_scope": True,
    }
