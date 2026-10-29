"""Tests for data-lineage cards, declared schemas, and dependency metadata."""

import pathlib
import re
from html import parser as html_parser

from support import rendering as rendering_support

from uptimely import compiler, project, spec
from uptimely.explorer.sections import data_lineage


class DataLineageStructureCollector(html_parser.HTMLParser):
    """Validate nesting and retain the parents of data-lineage layout elements."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str | None]]] = []
        self.parents: list[tuple[str, str | None]] = []
        self.columns: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "tr" and "data-column" in attributes:
            self.columns.append((attributes["data-column"], attributes.get("data-role")))
        if attributes.get("class") in {
            "data-lineage-stage",
            "data-lineage-step",
            "data-lineage-dependencies",
        }:
            parent = self.stack[-1][1]
            self.parents.append(
                (attributes["class"] or "", parent.get("id") or parent.get("class"))
            )
        if tag not in {"meta", "link", "br", "hr", "input", "img", "wbr"}:
            self.stack.append((tag, attributes))

    def handle_endtag(self, tag: str) -> None:
        assert self.stack, f"Unexpected closing {tag}"
        assert self.stack[-1][0] == tag, f"Closing {tag} inside {self.stack[-1][0]}"
        self.stack.pop()


def test_data_lineage_layout_has_balanced_stage_and_card_containers(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    plan = pump_bundle.execution_plan
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    collector = DataLineageStructureCollector()
    collector.feed(document)
    assert not collector.stack
    assert [parent for name, parent in collector.parents if name == "data-lineage-stage"] == [
        "data-lineage-board"
    ] * len(plan.execution_stages)
    assert [parent for name, parent in collector.parents if name == "data-lineage-step"] == [
        "data-lineage-stage"
    ] * len(plan.invocations)
    assert [
        parent for name, parent in collector.parents if name == "data-lineage-dependencies"
    ] == ["data-lineage-details"] * len(plan.invocations)


def test_data_lineage_tables_match_compiled_operations_and_producer_colors(
    pump_bundle: project.BuildBundle,
) -> None:
    spec_definition = pump_bundle.spec_definition
    plan = pump_bundle.execution_plan

    stages = data_lineage._build_stages(spec_definition, plan)

    assert [len(stage) for stage in stages] == [len(stage) for stage in plan.execution_stages]
    steps = {step.invocation_id: step for stage in stages for step in stage}
    numbers = {identifier: step.number for identifier, step in steps.items()}
    producers = {
        feature: steps[invocation.id]
        for invocation in plan.invocations
        for feature in invocation.output_features
        if feature not in spec_definition.dimensions
    }
    assert len({step.color for step in steps.values()}) == len(steps)
    for invocation in plan.invocations:
        step = steps[invocation.id]
        dimensions = spec_definition.entities[invocation.entity_id].dimension_ids
        assert step.dataset == invocation.dataset_id
        assert step.function_kind == invocation.function_kind
        assert step.dependencies == sorted(
            numbers[identifier] for identifier in invocation.dependency_ids
        )
        assert [column.name for column in step.columns if column.role == "Dimension"] == dimensions
        for role, features in (
            ("Input", invocation.input_features),
            ("Output", invocation.output_features),
        ):
            if invocation.function_kind == "escape":
                role = "Declared input" if role == "Input" else "Declared external output"
            assert [column.name for column in step.columns if column.role == role] == [
                feature for feature in features if feature not in dimensions
            ]
        for column in step.columns:
            if column.role == "Dimension":
                assert column.color == "#93c5fd"
                assert column.producer is None
                assert column.type == spec_definition.dimensions[column.name].type
            else:
                producer = producers[column.name]
                assert column.color == producer.color
                assert column.producer == producer.number
                if column.role in {"Output", "Declared external output"}:
                    assert producer.number == step.number
        if invocation.function_kind == "collapse":
            assert "timestamp" not in [column.name for column in step.columns]
        if invocation.function_kind == "write":
            assert not any(column.role == "Output" for column in step.columns)


def test_data_lineage_exports_every_table_and_dependency(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    plan = pump_bundle.execution_plan
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    tables = re.findall(
        r'<article class="data-lineage-step" id="step-(\d+)" data-invocation-id="([^"]+)"'
        r'\s+data-dependencies="([^"]*)"',
        document,
    )
    numbers = {invocation_id: number for number, invocation_id, _ in tables}
    assert set(numbers) == {invocation.id for invocation in plan.invocations}
    dependencies = {invocation_id: values for _, invocation_id, values in tables}
    for invocation in plan.invocations:
        assert dependencies[invocation.id].split(",") == (
            sorted((numbers[identifier] for identifier in invocation.dependency_ids), key=int)
            or [""]
        )
    assert document.count('<table class="data-lineage-table data-lineage-schema">') == len(
        plan.invocations
    )
    assert 'aria-label="Execution sections"' in document
    assert 'aria-label="Plan sections"' in document
    assert "Execution plan" not in document
    assert 'id="data-lineage-edges"' not in document
    assert "Illustration only:" in document
    assert "not calculated data" in document
    assert "No spec are executed" in document
    assert "Write boundary:" in document
    assert "No declared producer" not in document


def test_empty_data_lineage_has_explicit_empty_state(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.Spec()
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=compiler.Compiler().compile(spec_definition)
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    assert "No processing steps." in document
    assert '<table class="data-lineage-table"' not in document
    assert 'href="../execution/data-lineage.html" aria-current="page"' in document


def test_data_lineage_has_no_legend_badges(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.Spec()
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=compiler.Compiler().compile(spec_definition)
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    assert "data-lineage-legend" not in document
    assert "Data lineage color key" not in document


def test_data_lineage_has_focused_invocation_playback(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    styles = (tmp_path / "css/data_lineage.css").read_text(encoding="utf-8")
    script = (tmp_path / "js/data_lineage.js").read_text(encoding="utf-8")
    assert 'aria-label="Lineage playback" hidden' in document
    assert 'id="data-lineage-previous">Previous</button>' in document
    assert 'id="data-lineage-play" aria-pressed="false">Play</button>' in document
    assert 'id="data-lineage-next">Next</button>' in document
    assert 'id="data-lineage-step-track" role="list" aria-label="Execution steps"' in document
    assert 'class="data-lineage-step-position" id="data-lineage-position"' in document
    assert document.index('id="data-lineage-step-track"') < document.index(
        'id="data-lineage-position"'
    )
    assert 'class="data-lineage-stage-position" id="data-lineage-stage-position"' in document
    assert 'id="data-lineage-stage-track" role="list" aria-label="Execution stages"' in document
    execution_plan = pump_bundle.execution_plan
    execution_stages = execution_plan.execution_stages
    assert document.count('data-stage-marker="') == len(execution_stages)
    assert document.count('data-step-marker="') == sum(map(len, execution_stages))
    assert document.index('id="data-lineage-stage-track"') < document.index(
        'id="data-lineage-stage-position"'
    )
    assert "data-lineage-progress-track { display: flex; width: 100%;" in styles
    assert 'class="data-lineage-kicker"' not in document
    assert "Stage {{ stage_number }} / Step {{ step.number }}" not in document
    assert "Stage ${step.dataset.stage} of ${stages.length}" in script
    assert ".data-lineage-scene { display: grid; grid-template-columns: minmax(0, 1fr);" in styles
    assert 'class="data-lineage-arrow">' in document
    assert ".data-lineage-table-scroll { overflow-x: auto; overflow-y: hidden;" in styles
    assert ".data-lineage-step h3 {" in styles and "text-align: center;" in styles
    assert '<span class="data-lineage-arrow-icon" aria-hidden="true">&darr;</span>' in document
    assert "<h3>Maximum</h3>" in document
    assert (
        '<div class="data-lineage-arrow">\n'
        '            <span class="data-lineage-arrow-icon" aria-hidden="true">&darr;</span>\n'
        '            <small class="data-lineage-invocation-type">' in document
    )
    assert "<strong>maximum</strong>" not in document
    assert 'class="data-lineage-invocation-type">Aggregate</small>' in document
    assert "data-lineage-invocation-phase" not in document
    assert "<h3>Maximum</h3>" in document
    for function_kind in ("READ", "AGGREGATE", "VECTORIZE", "WRITE"):
        assert f'<span class="data-lineage-function-kind-label">{function_kind}</span>' in document
    assert '<span class="data-lineage-function-kind-label">FUNCTION_KIND</span>' not in document
    assert "data-lineage-step h3 {" in styles
    assert 'class="data-lineage-table-dataset">Dataset:' in document
    assert 'class="data-lineage-dataset"' not in document
    assert "transform: rotate(90deg)" not in document
    assert document.count("<summary>Declared schema and dependencies</summary>") == len(
        execution_plan.invocations
    )
    assert "<details open" not in document
    assert "data-lineage-inspector" not in document
    assert "data-lineage-direction" not in document
    assert "data-lineage-zoom" not in document
    assert "data-lineage-animate" not in document
    assert "<h3>Maximum</h3>" in document
    assert '<table class="data-lineage-table" data-side="input">' in document
    assert '<table class="data-lineage-table" data-side="output">' in document
    assert "prefers-reduced-motion: reduce" in script
    assert "reducedMotion.addEventListener" in script
    assert 'document.addEventListener("visibilitychange"' in script
    assert "three placeholder rows become one group" in document
    assert "Actual grouping and row counts are not known" in document
    assert "window.clearTimeout(timer)" in script
    assert 'type: "column"' in script
    assert 'type: "row"' in script
    assert 'type: "inputs"' in script
    assert 'type: "group"' in script
    assert 'type: "invocation"' in script
    assert 'type: "write"' in script
    assert "Exact input-to-output mappings are not inferred" in script
    assert "animation-play-state: paused" in styles
    assert 'step.classList.toggle("is-playing", playing)' in script
    assert "data-lineage-grouped" in styles


def test_visible_tables_preserve_every_declared_column(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    execution_plan = pump_bundle.execution_plan
    stages = data_lineage._build_stages(spec_definition, execution_plan)
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    collector = DataLineageStructureCollector()
    collector.feed(document)
    assert collector.columns == [
        (column.name, column.role) for stage in stages for step in stage for column in step.columns
    ]
    assert "This step" in document
    assert "Observation key" in document


def test_data_lineage_omits_declared_row_grain(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    dataset = next(iter(next(iter(spec_definition.entities.values())).datasets.values()))
    dataset.row_scope.grain = "<script>alert('grain')</script>"
    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    document = (tmp_path / "execution/data-lineage.html").read_text(encoding="utf-8")
    assert dataset.row_scope.grain not in document
    assert "&lt;script&gt;alert(&#39;grain&#39;)&lt;/script&gt;" not in document
