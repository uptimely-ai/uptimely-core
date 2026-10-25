"""Explorer rendering requires and preserves the supplied execution plan."""

import dataclasses
import pathlib

import pytest
from conftest import EXAMPLES_ROOT, example_bundle

from uptimely import compiler, spec
from uptimely import execution_plan as plan_module
from uptimely.explorer import explorer

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
SAVED_PLAN_MARKER = "saved-plan-only-marker"


def test_render_saved_plan_without_compiling(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    compiled = example_bundle().execution_plan
    first, *remaining = compiled.callables
    custom = dataclasses.replace(
        first, arguments={**first.arguments, "saved_plan_marker": SAVED_PLAN_MARKER}
    )
    supplied = dataclasses.replace(compiled, callables=[custom, *remaining])
    path = tmp_path / "plan.json"
    plan_module.export_json(supplied, path)
    supplied = plan_module.from_json(path)
    original = plan_module.to_dict(supplied)

    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("A supplied plan must not be recompiled")

    monkeypatch.setattr(compiler.Compiler, "compile", fail_compile)
    target = tmp_path / "website/index.html"
    index = explorer.Explorer(definition, plan=supplied).create_html(target)

    assert index.is_file()
    for page in ("plan/graph.html", "plan/stages.html"):
        assert SAVED_PLAN_MARKER in (index.parent / page).read_text(encoding="utf-8")
    assert (index.parent / "execution/data_lineage.html").is_file()
    assert plan_module.to_dict(supplied) == original


def test_explorer_requires_existing_plan() -> None:
    definition = spec.load_spec(SPEC_PATH)

    with pytest.raises(TypeError, match="plan"):
        explorer.Explorer(definition)  # type: ignore[call-arg]


def test_explorer_distinguishes_full_model_from_scoped_plan(
    tmp_path: pathlib.Path,
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    plan = example_bundle(features=("health_signal_normalized",)).execution_plan
    index = explorer.Explorer(
        definition,
        plan=plan,
        features=["health_signal_normalized"],
    ).create_html(tmp_path / "index.html")
    document = index.read_text(encoding="utf-8")

    assert "Partial build" in document
    assert "Spec: complete model" in document
    assert "Plan and execution: selected features: health_signal_normalized" in document
    assert "Plan and execution: selected features: health_signal_normalized" in (
        index.parent / "plan/overview.html"
    ).read_text(encoding="utf-8")
