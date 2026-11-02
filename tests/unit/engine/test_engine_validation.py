"""Engine-level configuration validation."""

import logging

import pytest

from uptimely import execution_plan
from uptimely.engine import validation
from uptimely.engine.dataframe import backend


def test_engine_validator_accepts_matching_backend(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=validation.__name__)
    plan = execution_plan.ExecutionPlan(3, "polars", {}, [], [])
    polars_backend = backend.PolarsBackend()
    validator = validation.EngineValidator(plan, polars_backend)

    assert validator.plan is plan
    assert validator.backend is polars_backend
    validator.validate()
    assert caplog.messages == [
        "Checking plan backend compatibility: required=polars, configured=polars"
    ]


def test_engine_validator_rejects_mismatched_backend() -> None:
    plan = execution_plan.ExecutionPlan(3, "pandas", {}, [], [])
    validator = validation.EngineValidator(plan, backend.PolarsBackend())

    with pytest.raises(ValueError, match=r"Unsupported plan backend: pandas\. Expected polars\."):
        validator.validate()
