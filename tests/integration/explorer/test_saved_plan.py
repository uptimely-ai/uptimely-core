"""Explorer rendering requires and preserves the supplied execution plan."""

import dataclasses
import pathlib
from collections import abc

import pytest
from conftest import EXAMPLES_ROOT, example_bundle

from uptimely import compiler, spec
from uptimely import execution_plan as plan_module
from uptimely.explorer import explorer, render
from uptimely.explorer.sections import data_lineage, feature_graph
from uptimely.explorer.sections import plan as plan_section
from uptimely.explorer.sections import spec as spec_section

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
SAVED_PLAN_MARKER = "saved-plan-only-marker"


def test_explorer_shares_one_website_context_between_sections(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    supplied = example_bundle(features=("health_signal_normalized",)).execution_plan
    contexts: list[render.WebsiteContext] = []
    section_ids: list[str] = []
    write_pages = render.WebsiteSection.write_pages

    def record_write(
        section: render.WebsiteSection,
        output_directory: pathlib.Path,
        website: render.WebsiteContext,
        data: abc.Mapping[str, object],
    ) -> None:
        contexts.append(website)
        section_ids.append(section.active_page)
        assert not {"project_name", "index_filename", "execution_scope", "is_scoped"} & data.keys()
        write_pages(section, output_directory, website, data)

    monkeypatch.setattr(render.WebsiteSection, "write_pages", record_write)
    explorer.Explorer(definition, plan=supplied, features=["health_signal_normalized"]).create_html(
        tmp_path / "custom.html"
    )

    assert section_ids == ["spec", "graph", "plan", "execution"]
    assert all(website is contexts[0] for website in contexts)
    assert contexts[0] == render.WebsiteContext(
        project_name=definition.name,
        index_filename="custom.html",
        execution_scope="selected features: health_signal_normalized",
        is_scoped=True,
    )


def test_section_context_builders_do_not_write_files(tmp_path: pathlib.Path) -> None:
    definition = spec.load_spec(SPEC_PATH)
    supplied = example_bundle().execution_plan
    output_directory = tmp_path / "not-created"
    contexts = [
        spec_section.build_context(spec_section._build_context(definition, False)),
        feature_graph.build_context(spec.FeatureGraph(definition)),
        plan_section.build_context(supplied, output_directory),
        data_lineage.build_context(definition, supplied),
    ]

    assert all(contexts)
    assert not output_directory.exists()
    assert not list(tmp_path.iterdir())


def test_render_saved_plan_without_compiling(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition = spec.load_spec(SPEC_PATH)
    compiled = example_bundle().execution_plan
    first, *remaining = compiled.invocations
    custom = dataclasses.replace(
        first, arguments={**first.arguments, "saved_plan_marker": SAVED_PLAN_MARKER}
    )
    supplied = dataclasses.replace(compiled, invocations=[custom, *remaining])
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
