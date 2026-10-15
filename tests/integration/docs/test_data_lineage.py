"""Tests for lineage cards, declared schemas, and dependency metadata."""

import pathlib
import re
from html import parser as html_parser

from uptimely import compile, spec
from uptimely.docs import docs, lineage

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


class LineageStructureCollector(html_parser.HTMLParser):
    """Validate nesting and retain the parents of lineage layout elements."""

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
            "lineage-stage",
            "lineage-step",
            "lineage-dependencies",
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


def test_lineage_layout_has_balanced_stage_and_card_containers(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    plan = compile.Compiler(specification).compile()
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    collector = LineageStructureCollector()
    collector.feed(document)
    assert not collector.stack
    assert [parent for name, parent in collector.parents if name == "lineage-stage"] == [
        "lineage-board"
    ] * len(plan.execution_stages)
    assert [parent for name, parent in collector.parents if name == "lineage-step"] == [
        "lineage-stage"
    ] * len(plan.operations)
    assert [parent for name, parent in collector.parents if name == "lineage-dependencies"] == [
        "lineage-details"
    ] * len(plan.operations)


def test_lineage_tables_match_compiled_operations_and_producer_colors() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    plan = compile.Compiler(specification).compile()

    stages = lineage._build_stages(specification, plan)

    assert [len(stage) for stage in stages] == [len(stage) for stage in plan.execution_stages]
    steps = {step.operation_id: step for stage in stages for step in stage}
    numbers = {identifier: step.number for identifier, step in steps.items()}
    producers = {
        feature: steps[operation.id]
        for operation in plan.operations
        for feature in operation.output_features
        if feature not in specification.dimensions
    }
    assert len({step.color for step in steps.values()}) == len(steps)
    for operation in plan.operations:
        step = steps[operation.id]
        dimensions = specification.entities[operation.entity_id].dimension_ids
        assert step.dataset == operation.dataset_id
        assert step.kind == operation.kind
        assert step.dependencies == sorted(
            numbers[identifier] for identifier in operation.dependency_ids
        )
        assert [column.name for column in step.columns if column.role == "Dimension"] == dimensions
        for role, features in (
            ("Input", operation.input_features),
            ("Output", operation.output_features),
        ):
            assert [column.name for column in step.columns if column.role == role] == [
                feature for feature in features if feature not in dimensions
            ]
        for column in step.columns:
            if column.role == "Dimension":
                assert column.color == "#93c5fd"
                assert column.producer is None
                assert column.type == specification.dimensions[column.name].type
            else:
                producer = producers[column.name]
                assert column.color == producer.color
                assert column.producer == producer.number
                if column.role == "Output":
                    assert producer.number == step.number
        if operation.kind == "collapse":
            assert "timestamp" not in [column.name for column in step.columns]
        if operation.kind == "write":
            assert not any(column.role == "Output" for column in step.columns)


def test_lineage_exports_every_table_and_dependency(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    plan = compile.Compiler(specification).compile()
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    tables = re.findall(
        r'<article class="lineage-step" id="step-(\d+)" data-operation="([^"]+)"'
        r'\s+data-dependencies="([^"]*)"',
        document,
    )
    numbers = {operation_id: number for number, operation_id, _ in tables}
    assert set(numbers) == {operation.id for operation in plan.operations}
    dependencies = {operation_id: values for _, operation_id, values in tables}
    for operation in plan.operations:
        assert dependencies[operation.id].split(",") == (
            sorted((numbers[identifier] for identifier in operation.dependency_ids), key=int)
            or [""]
        )
    assert document.count('<table class="lineage-table lineage-schema">') == len(plan.operations)
    assert 'aria-label="Execution sections"' in document
    assert 'aria-label="Plan sections"' in document
    assert "Execution plan" not in document
    assert 'id="lineage-edges"' not in document
    assert "Illustration only:" in document
    assert "not calculated data" in document
    assert "No analytics are executed" in document
    assert "Write boundary:" in document
    assert "No declared producer" not in document


def test_empty_lineage_has_explicit_empty_state(tmp_path: pathlib.Path) -> None:
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert "No processing steps." in document
    assert '<table class="lineage-table"' not in document
    assert 'href="../execution/data_lineage.html" aria-current="page"' in document


def test_lineage_has_no_legend_badges(tmp_path: pathlib.Path) -> None:
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert "lineage-legend" not in document
    assert "Data lineage color key" not in document


def test_lineage_has_focused_callable_playback(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert 'aria-label="Lineage playback" hidden' in document
    assert 'id="lineage-previous">Previous</button>' in document
    assert 'id="lineage-play" aria-pressed="false">Play</button>' in document
    assert 'id="lineage-next">Next</button>' in document
    assert 'id="lineage-step-track" role="list" aria-label="Execution steps"' in document
    assert 'class="lineage-step-position" id="lineage-position"' in document
    assert document.index('id="lineage-step-track"') < document.index('id="lineage-position"')
    assert 'class="lineage-stage-position" id="lineage-stage-position"' in document
    assert 'id="lineage-stage-track" role="list" aria-label="Execution stages"' in document
    execution_stages = compile.Compiler(specification).compile().execution_stages
    assert document.count('data-stage-marker="') == len(execution_stages)
    assert document.count('data-step-marker="') == sum(map(len, execution_stages))
    assert document.index('id="lineage-stage-track"') < document.index(
        'id="lineage-stage-position"'
    )
    assert "lineage-progress-track { display: flex; width: 100%;" in document
    assert 'class="lineage-kicker"' not in document
    assert "Stage {{ stage_number }} / Step {{ step.number }}" not in document
    assert "Stage ${step.dataset.stage} of ${stages.length}" in document
    assert ".lineage-scene { display: grid; grid-template-columns: minmax(0, 1fr);" in document
    assert 'class="lineage-arrow">' in document
    assert ".lineage-table-scroll { overflow-x: auto; overflow-y: hidden;" in document
    assert ".lineage-step h3 {" in document and "text-align: center;" in document
    assert '<span class="lineage-arrow-icon" aria-hidden="true">&darr;</span>' in document
    assert "<h3>Maximum</h3>" in document
    assert (
        '<div class="lineage-arrow">\n'
        '            <span class="lineage-arrow-icon" aria-hidden="true">&darr;</span>\n'
        '            <small class="lineage-callable-type">' in document
    )
    assert "<strong>maximum</strong>" not in document
    assert 'class="lineage-callable-type">Aggregate</small>' in document
    assert "lineage-callable-phase" not in document
    assert "<h3>Maximum</h3>" in document
    for operation_type in ("READ", "AGGREGATE", "VECTORIZE", "WRITE"):
        assert f'<span class="lineage-operation-label">{operation_type}</span>' in document
    assert '<span class="lineage-operation-label">OPERATION</span>' not in document
    assert "lineage-step h3 {" in document
    assert 'class="lineage-table-dataset">Dataset:' in document
    assert 'class="lineage-dataset"' not in document
    assert "transform: rotate(90deg)" not in document
    assert document.count("<summary>Declared schema and dependencies</summary>") == len(
        compile.Compiler(specification).compile().operations
    )
    assert "<details open" not in document
    assert "lineage-inspector" not in document
    assert "lineage-direction" not in document
    assert "lineage-zoom" not in document
    assert "lineage-animate" not in document
    assert "<h3>Maximum</h3>" in document
    assert '<table class="lineage-table" data-side="input">' in document
    assert '<table class="lineage-table" data-side="output">' in document
    assert "prefers-reduced-motion: reduce" in document
    assert "reducedMotion.addEventListener" in document
    assert 'document.addEventListener("visibilitychange"' in document
    assert "three placeholder rows become one group" in document
    assert "Actual grouping and row counts are not known" in document
    assert "window.clearTimeout(timer)" in document
    assert 'type: "column"' in document
    assert 'type: "row"' in document
    assert 'type: "inputs"' in document
    assert 'type: "group"' in document
    assert 'type: "callable"' in document
    assert 'type: "write"' in document
    assert "Exact input-to-output mappings are not inferred" in document
    assert "animation-play-state: paused" in document
    assert 'step.classList.toggle("is-playing", playing)' in document
    assert "lineage-grouped" in document


def test_visible_tables_preserve_every_declared_column(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    execution_plan = compile.Compiler(specification).compile()
    stages = lineage._build_stages(specification, execution_plan)
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    collector = LineageStructureCollector()
    collector.feed(document)
    assert collector.columns == [
        (column.name, column.role) for stage in stages for step in stage for column in step.columns
    ]
    assert "This step" in document
    assert "Observation key" in document


def test_lineage_omits_declared_row_grain(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    dataset = next(iter(specification.entities.values())).datasets[0]
    dataset.row_scope.grain = "<script>alert('grain')</script>"
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert dataset.row_scope.grain not in document
    assert "&lt;script&gt;alert(&#39;grain&#39;)&lt;/script&gt;" not in document
