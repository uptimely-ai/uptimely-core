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
        id="read",
        semantics=types.SimpleNamespace(
            function_id="read",
            profile_id="telemetry",
            output_features=["reading"],
            operator_id="source",
        ),
    )
    execution_plan = unittest.mock.Mock(spec=plan_module.ExecutionPlan)
    execution_plan.invocations_by_id = {}
    execution_plan.input_invocations = {"read": []}
    execution_plan.execution_stages = [[invocation]]

    plan.log_stages(execution_plan)

    assert caplog.messages == [
        "\nExecution stages",
        "Stage 1",
        "read(telemetry) -> reading",
    ]


def test_stages_show_explicit_input_producers(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=plan.__name__)
    execution_plan = plan_module.from_dict(
        {
            "plan_version": plan_module.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "read",
                    "entrypoint": "test:read",
                    "arguments": {},
                    "returns": "$datasets.telemetry.read",
                    "semantics": {
                        "role": "compute",
                        "result": "target",
                        "function_id": "read",
                        "profile_id": "telemetry",
                        "operator_id": "read",
                        "output_features": ["reading"],
                    },
                },
                {
                    "id": "process",
                    "entrypoint": "test:process",
                    "arguments": {"dataset": "$datasets.telemetry.read"},
                    "returns": "$datasets.telemetry.process",
                    "semantics": {
                        "role": "compute",
                        "result": "target",
                        "function_id": "process",
                        "profile_id": "telemetry",
                        "operator_id": "process",
                        "output_features": ["result"],
                    },
                },
            ],
            "stages": [["read", "process"]],
            "datasets": {"telemetry": "$datasets.telemetry.process"},
        }
    )

    plan.log_stages(execution_plan)

    assert caplog.messages[-1] == "process(telemetry) -> result <- [read]"
