"""Tests that Explorer presentation data uses the supplied execution plan."""

import copy
import json

import pytest

from uptimely import application, compiler
from uptimely import plan as plan_module
from uptimely.explorer import presentation

SAVED_PLAN_MARKER = "saved-plan-only-marker"


def test_presentation_uses_saved_plan_without_recompiling(
    monkeypatch: pytest.MonkeyPatch,
    pump_bundle: application.BuildBundle,
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


def test_topology_preserves_invocation_ids_from_the_supplied_plan(
    pump_bundle: application.BuildBundle,
) -> None:
    definition = pump_bundle.spec_definition
    compiled = pump_bundle.execution_plan
    original = presentation.build_presentation_data(definition, compiled)
    original_links = original["graphs"]["invocation_lineage"]["links"]
    old_id = original_links[0]["source"]
    new_id = "custom-invocation-id"
    supplied = copy.replace(
        compiled,
        invocations=[
            copy.replace(invocation, id=new_id) if invocation.id == old_id else invocation
            for invocation in compiled.invocations
        ],
        stages=[
            plan_module.Stage([new_id if item == old_id else item for item in stage])
            for stage in compiled.stages
        ],
    )

    rebuilt = presentation.build_presentation_data(definition, supplied)
    links = rebuilt["graphs"]["invocation_lineage"]["links"]
    assert {
        (
            new_id if link["source"] == old_id else link["source"],
            new_id if link["target"] == old_id else link["target"],
        )
        for link in original_links
    } == {(link["source"], link["target"]) for link in links}
