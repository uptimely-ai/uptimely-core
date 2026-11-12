"""Test analytical response policy independently of engine execution and MCP."""

import dataclasses

import polars as pl
import pytest

from uptimely import engine, project
from uptimely.mcp import results

TARGET = ("pump_telemetry", "pump_health_score")


def _result(bundle: project.BuildBundle) -> engine.ExecutionResult:
    """Create a completed result without running project functions."""
    return engine.ExecutionResult(
        datasets={},
        calculated_outputs={
            (profile_id, feature): None
            for feature, (
                profile_id,
                _,
            ) in bundle.spec_definition.calculated_feature_producers.items()
        },
        invocation_statuses={},
        durations={},
        failures={},
        plan_version=bundle.execution_plan.plan_version,
    )


def test_full_build_reports_late_failure_as_warning(pump_bundle: project.BuildBundle) -> None:
    result = dataclasses.replace(
        _result(pump_bundle),
        failures={"writer": "Write failed"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result)

    assert payload["status"] == "ok"
    assert payload["warnings"] == result.failures
    assert "failures" not in payload


def test_full_build_reports_missing_outputs_as_failure(pump_bundle: project.BuildBundle) -> None:
    result = dataclasses.replace(
        _result(pump_bundle),
        calculated_outputs={},
        failures={"reader": "Read failed"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result)

    assert payload["status"] == "failed"
    assert payload["failures"] == result.failures
    assert payload["datasets"] == []


def test_targeted_run_keeps_execution_failure(pump_bundle: project.BuildBundle) -> None:
    result = dataclasses.replace(
        _result(pump_bundle), failures={"calculation": "Calculation failed"}
    )

    payload = results.ExecutionResponse.format(pump_bundle, result, TARGET)

    assert payload["status"] == "failed"
    assert payload["failures"] == result.failures
    assert payload["datasets"] == []
    assert payload["target"] == {"profile": TARGET[0], "operator": TARGET[1]}


def test_unrelated_preview_failure_does_not_fail_target(pump_bundle: project.BuildBundle) -> None:
    identifiers = pump_bundle.spec_definition.identifiers_by_profile[TARGET[0]]
    frame = pl.DataFrame({name: [] for name in [*identifiers, TARGET[1], "unrequested"]})
    result = dataclasses.replace(
        _result(pump_bundle),
        preview_frames={TARGET[0]: frame},
        preview_failures={"unrelated_profile": "Cannot collect"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result, TARGET)

    assert payload["status"] == "ok"
    assert "preview_failures" not in payload
    assert payload["datasets"] == [
        {
            "profile": TARGET[0],
            "features": [TARGET[1]],
            "columns": [*identifiers, TARGET[1]],
            "row_count": 0,
            "rows": [],
        }
    ]


def test_missing_preview_without_engine_failure_is_explicit(
    pump_bundle: project.BuildBundle,
) -> None:
    with pytest.raises(TypeError, match="without a serializable dataset preview"):
        results.ExecutionResponse.format(pump_bundle, _result(pump_bundle), TARGET)
