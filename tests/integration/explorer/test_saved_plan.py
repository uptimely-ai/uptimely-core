"""Tests that Explorer presentation data uses the supplied execution plan."""

import copy
import json

import pytest

from uptimely import compiler, project
from uptimely import plan as plan_module
from uptimely.explorer import presentation

SAVED_PLAN_MARKER = "saved-plan-only-marker"


def test_presentation_uses_saved_plan_without_recompiling(
    monkeypatch: pytest.MonkeyPatch,
    pump_bundle: project.BuildBundle,
) -> None:
    definition = pump_bundle.spec_definition
    compiled = pump_bundle.execution_plan
    first, *remaining = compiled.invocations
    custom = copy.replace(
        first, arguments={**first.arguments, "saved_plan_marker": SAVED_PLAN_MARKER}
    )
    supplied = copy.replace(compiled, invocations=[custom, *remaining])
    original = plan_module.to_dict(supplied)

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("A supplied plan must not be recompiled")

    monkeypatch.setattr(compiler.Compiler, "compile", fail_compile)
    data = presentation.build_presentation_data(definition, supplied)

    assert SAVED_PLAN_MARKER in json.dumps(data)
    assert plan_module.to_dict(supplied) == original
    assert data["plan"]["invocation_count"] == len(supplied.invocations)
