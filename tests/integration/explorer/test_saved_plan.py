"""Saved execution plans are rendered as supplied, without recompilation."""

import dataclasses
import pathlib

import pytest

from uptimely import compiler, spec
from uptimely.compiler import plan as plan_module
from uptimely.explorer import explorer

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")
SAVED_PLAN_MARKER = "saved-plan-only-marker"


@pytest.mark.parametrize("use_helper", [False, True])
def test_render_saved_plan_without_compiling(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, use_helper: bool
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    compiled = compiler.Compiler(definition).compile()
    first, *remaining = compiled.callables
    custom = dataclasses.replace(
        first, arguments={**first.arguments, "saved_plan_marker": SAVED_PLAN_MARKER}
    )
    supplied = plan_module.ExecutionPlan(
        dataclasses.replace(compiled.plan, callables=[custom, *remaining])
    )
    path = tmp_path / "plan.json"
    supplied.export_json(path)
    supplied = plan_module.ExecutionPlan.from_json(path)
    original = supplied.plan.to_dict()

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("A supplied plan must not be recompiled")

    monkeypatch.setattr(compiler.Compiler, "compile", fail_compile)
    target = tmp_path / "website/index.html"
    if use_helper:
        index = explorer.create_html(definition, target, plan=supplied)
    else:
        index = explorer.Explorer(definition, plan=supplied).create_html(target)

    assert index.is_file()
    for page in ("plan/graph.html", "plan/stages.html"):
        assert SAVED_PLAN_MARKER in (index.parent / page).read_text(encoding="utf-8")
    assert (index.parent / "execution/data_lineage.html").is_file()
    assert supplied.plan.to_dict() == original


def test_explorer_compiles_when_no_plan_is_supplied(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    original_compile = compiler.Compiler.compile
    calls: list[compiler.Compiler] = []

    def record_compile(instance: compiler.Compiler) -> plan_module.ExecutionPlan:
        calls.append(instance)
        return original_compile(instance)

    monkeypatch.setattr(compiler.Compiler, "compile", record_compile)

    explorer.create_html(definition, tmp_path / "index.html")

    assert len(calls) == 1
