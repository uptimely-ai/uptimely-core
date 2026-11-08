"""Execution-stage log formatting tests."""

import logging
import types
import unittest.mock

import pytest

from uptimely import plan as plan_module
from uptimely.cli import plan


def test_stage_invocations_are_not_indented(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=plan.__name__)
    invocation = types.SimpleNamespace(
        dependency_ids=[],
        function_id="read",
        profile_id="telemetry",
        output_features=["reading"],
        operator_id="source",
    )
    execution_plan = unittest.mock.Mock(spec=plan_module.ExecutionPlan)
    execution_plan.invocations_by_id = {}
    execution_plan.execution_stages = [[invocation]]

    plan.log_stages(execution_plan)

    assert caplog.messages == [
        "\nExecution stages",
        "Stage 1",
        "read(telemetry) -> reading",
    ]
