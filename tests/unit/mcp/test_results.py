"""Test analytical response policy independently of engine execution and MCP."""

import dataclasses

import polars as pl
import pytest
from support import examples as example_support

from uptimely import application, engine
from uptimely.mcp import results

TARGET_PROFILE = "pump_telemetry"
TARGET_FEATURE = "pump_health_score"


def _target(bundle: application.BuildBundle) -> tuple[str, str]:
    """Return the operator producing the selected health-score feature."""
    profile = bundle.spec_definition.profiles[TARGET_PROFILE]
    operator_id = example_support.operator_id_for_output(profile.assembly, TARGET_FEATURE)
    return TARGET_PROFILE, operator_id


def _result(bundle: application.BuildBundle) -> engine.ExecutionResult:
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


def test_full_build_reports_late_failure_as_warning(pump_bundle: application.BuildBundle) -> None:
    result = dataclasses.replace(
        _result(pump_bundle),
        failures={"writer": "Write failed"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result)

    assert payload["status"] == "ok"
    assert payload["warnings"] == result.failures
    assert "failures" not in payload


def test_full_build_reports_missing_outputs_as_failure(
    pump_bundle: application.BuildBundle,
) -> None:
    result = dataclasses.replace(
        _result(pump_bundle),
        calculated_outputs={},
        failures={"reader": "Read failed"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result)

    assert payload["status"] == "failed"
    assert payload["failures"] == result.failures
    assert payload["datasets"] == []


def test_targeted_run_keeps_execution_failure(pump_bundle: application.BuildBundle) -> None:
    target = _target(pump_bundle)
    result = dataclasses.replace(
        _result(pump_bundle), failures={"calculation": "Calculation failed"}
    )

    payload = results.ExecutionResponse.format(pump_bundle, result, target)

    assert payload["status"] == "failed"
    assert payload["failures"] == result.failures
    assert payload["datasets"] == []
    assert payload["target"] == {"profile": target[0], "operator": target[1]}


def test_unrelated_preview_failure_does_not_fail_target(
    pump_bundle: application.BuildBundle,
) -> None:
    target = _target(pump_bundle)
    identifiers = pump_bundle.spec_definition.identifiers_by_profile[TARGET_PROFILE]
    frame = pl.DataFrame({name: [] for name in [*identifiers, TARGET_FEATURE, "unrequested"]})
    result = dataclasses.replace(
        _result(pump_bundle),
        preview_frames={TARGET_PROFILE: frame},
        preview_failures={"unrelated_profile": "Cannot collect"},
    )

    payload = results.ExecutionResponse.format(pump_bundle, result, target)

    assert payload["status"] == "ok"
    assert "preview_failures" not in payload
    assert payload["datasets"] == [
        {
            "profile": TARGET_PROFILE,
            "features": [TARGET_FEATURE],
            "columns": [*identifiers, TARGET_FEATURE],
            "row_count": 0,
            "rows": [],
        }
    ]


def test_missing_preview_without_engine_failure_is_explicit(
    pump_bundle: application.BuildBundle,
) -> None:
    target = _target(pump_bundle)
    with pytest.raises(TypeError, match="without a serializable dataset preview"):
        results.ExecutionResponse.format(pump_bundle, _result(pump_bundle), target)
