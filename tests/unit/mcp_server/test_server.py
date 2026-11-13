"""In-memory client tests for the uptimely MCP server."""

import dataclasses
import json
import logging
import pathlib
import shlex
import sys

import pytest
from example.src import external_workflow
from support import examples as example_support

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

import fastmcp as fastmcp_  # noqa: E402

from uptimely import compiler, engine  # noqa: E402
from uptimely import plan as plan_module  # noqa: E402
from uptimely.mcp import server  # noqa: E402
from uptimely.mcp import state as mcp_state  # noqa: E402
from uptimely.project import paths  # noqa: E402
from uptimely.run import store as run_store  # noqa: E402
from uptimely.spec import model as spec_model  # noqa: E402

PROJECT_ROOT = example_support.EXAMPLES_ROOT
CONFIG_PATH = example_support.EXAMPLES_ROOT / "config" / "config.json"


@pytest.fixture()
def state(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> mcp_state.ServerState:
    """Provide server state bound to the pump analytics build."""
    root = example_project_factory(tmp_path / "project")
    config = mcp_state.ServerState.load_config(CONFIG_PATH, root)
    return mcp_state.ServerState(
        project_root=root,
        config=config,
    )


def test_load_config_defaults_to_project_config(tmp_path: pathlib.Path) -> None:
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    (config_directory / "config.json").write_text(
        '{"engine": {"backend": {"dataframe": "polars"}}, "params": {"threshold": 10}}',
        encoding="utf-8",
    )

    config = mcp_state.ServerState.load_config(None, tmp_path)

    assert config.engine.backend.dataframe == "polars"
    assert config.params.root == {"threshold": 10}


async def _call(state: mcp_state.ServerState, tool: str, arguments: dict | None = None) -> dict:
    """Call one tool over the in-memory transport and decode its JSON payload."""
    async with fastmcp_.Client(server.create_server(state)) as client:
        result = await client.call_tool(tool, arguments or {})
    return json.loads(result.content[0].text)


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
    assert all("kind" not in function for function in payload)


@pytest.mark.anyio
async def test_describe_function_resolves_signature(state: mcp_state.ServerState) -> None:
    """describe_function returns declared args and the resolved Python signature."""
    payload = await _call(state, "describe_function", {"function_id": "pump_health_score"})
    assert payload["category"] == "calculate"
    assert "kind" not in payload
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
        "operator": "pump_health_score",
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
        entrypoint="example.src.analytics:aggregate",
    )
    dataset = definition.profiles["pump_telemetry"]
    dataset.assembly["external_audit"] = spec_model.Operator(
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
            "grain_relationships": [{"source_profile": "pump_telemetry", "relationship": "same"}],
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
        "recommended_discharge_pressure",
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
    telemetry = next(
        dataset for dataset in payload["datasets"] if "pump_health_score" in dataset["features"]
    )
    assert telemetry["profile"] == "pump_telemetry"
    assert telemetry["row_count"] == 3
    assert {
        "pump_id",
        "timestamp",
        "pump_health_score",
    } <= set(telemetry["columns"])
    assert {"pump_id", "pump_health_score"} <= set(telemetry["rows"][0])
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
    assert payload["spec"].endswith("_generated/build/spec.json")
    assert payload["profiles"] == [
        "constants",
        "pump",
        "pump_category",
        "pump_series",
        "pump_telemetry",
        "pump_telemetry_by_day",
        "pump_telemetry_by_hour",
        "pump_telemetry_by_minute",
    ]


@pytest.mark.anyio
async def test_missing_build_fails_with_recovery_command(tmp_path: pathlib.Path) -> None:
    """MCP reports missing saved builds explicitly instead of loading source files."""
    project_root = tmp_path / "missing project"
    state = mcp_state.ServerState(project_root=project_root)

    with pytest.raises(Exception, match="uptimely project build") as error:
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
    operator = next(item for item in payload if item["operator"] == "pump_health_score")

    assert operator == {
        "profile": "pump_telemetry",
        "operator": "pump_health_score",
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
    arguments = (
        {"profile_id": "pump_telemetry", "operator_id": "pump_health_score"}
        if tool == "execute_operator"
        else {"function_id": "pump_health_score"}
    )

    payload = await _call(state, tool, {**arguments, "max_rows": 2})

    assert payload["status"] == "ok"
    assert payload["target"] == {"profile": "pump_telemetry", "operator": "pump_health_score"}
    assert len(payload["datasets"]) == 1
    dataset = payload["datasets"][0]
    assert dataset["features"] == ["pump_health_score"]
    assert dataset["row_count"] == 2
    assert set(dataset["columns"]) == {
        *bundle.spec_definition.identifiers_by_profile["pump_telemetry"],
        "pump_health_score",
    }
    saved = run_store.RunStore(state.project_root).read_manifest()
    selected = bundle.execution_plan.for_operator("pump_telemetry", "pump_health_score")
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
        {"function_id": "operation_point_quantum_optimization", "max_rows": 1},
    )

    assert payload["status"] == "ok"
    assert payload["datasets"][0]["features"] == ["operating_point_recommendation"]
    row = payload["datasets"][0]["rows"][0]
    assert row["pump_id"] == "PUMP-101"
    assert row["timestamp"] == "2026-09-01T08:00:00+00:00"
    assert row["operating_point_recommendation"] == {
        "recommended_flow_rate": 118.0,
        "recommended_discharge_pressure": 5.3,
        "energy_cost_score": pytest.approx(17.9 / 118.0),
        "converged": True,
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
    async with fastmcp_.Client(server.create_server(state)) as client:
        with pytest.raises(Exception, match=message):
            await client.call_tool(tool, arguments)


@pytest.mark.anyio
async def test_targeted_execution_rejects_operators_outside_saved_scope(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> None:
    root = example_project_factory(tmp_path / "scoped", features=("pressure_flow_efficiency",))
    state = mcp_state.ServerState(root)
    listing = await _call(state, "list_operators")
    assert not next(
        item for item in listing if item["operator"] == "process_pump_external_workflow"
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
    runtime = engine.Engine(bundle, state.config)
    original_execute = runtime._execute

    def execute(
        *, validate: bool, plan: plan_module.ExecutionPlan | None = None
    ) -> engine.ExecutionResult:
        logging.getLogger(__name__).warning("Source observations are delayed")
        return original_execute(validate=validate, plan=plan)

    monkeypatch.setattr(runtime, "_execute", execute)
    runtime.run(operator=("pump_telemetry", "pressure_flow_efficiency"), preview_rows=1)
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
    state = mcp_state.ServerState(tmp_path)
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
    monkeypatch.setattr(external_workflow, "process_pump_external_workflow", lambda: None)

    payload = await _call(
        state, "execute_function", {"function_id": "process_pump_external_workflow", "max_rows": 1}
    )

    assert payload["status"] == "failed"
    assert payload["datasets"] == []
    assert "ratio" in payload["output_failures"]["pump"]
