"""Engine-level configuration validation."""

import logging

import pytest
from support import execution as execution_support

from uptimely import plan as execution_plan


def test_engine_checks_matching_backend(
    caplog: pytest.LogCaptureFixture, engine_for_plan: execution_support.EngineFactory
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.engine.engine")
    plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[],
        stages=[],
    )
    engine = engine_for_plan(plan)

    assert engine.plan == plan
    assert engine.backend.name == "polars"
    assert caplog.messages == [
        "Checking plan backend compatibility: required=polars, configured=polars"
    ]


def test_engine_rejects_mismatched_backend(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="pandas",
        invocations=[],
        stages=[],
    )

    with pytest.raises(ValueError, match=r"Unsupported plan backend: pandas\. Expected polars\."):
        engine_for_plan(plan)
