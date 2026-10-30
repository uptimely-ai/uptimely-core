"""Tests for data-lineage cards, declared schemas, and dependency metadata."""

import pathlib
import re
from html import parser as html_parser

import pytest
from support import rendering as rendering_support

from uptimely import compiler, execution_plan, project, spec
from uptimely.explorer import render
from uptimely.explorer.sections import data_lineage
from uptimely.spec import functions


@pytest.mark.parametrize(
    ("kind", "source_dimensions", "target_dimensions", "source_rows", "target_rows"),
    [
        ("collapse", ["id", "time"], ["id"], 3, 1),
        ("expand", ["id"], ["id", "time"], 1, 3),
        ("conform", ["id"], ["id"], 3, 3),
    ],
)
def test_transfer_tables_show_source_grain_and_shared_keys(
    kind: functions.FunctionKindId,
    source_dimensions: list[str],
    target_dimensions: list[str],
    source_rows: int,
    target_rows: int,
) -> None:
    definition = spec.Spec.model_validate(
        {
            "dimensions": {"id": {"type": "integer"}, "time": {"type": "integer"}},
            "entities": {
                name: {
                    "name": name,
                    "dimensions": dimensions,
                    "datasets": {name: {"features": {feature: {"type": "float"}}}},
                }
                for name, dimensions, feature in (
                    ("source", source_dimensions, "input_value"),
                    ("target", target_dimensions, "result"),
                )
            },
        }
    )
    invocation = execution_plan.Invocation(
        id="transfer",
        function_kind=kind,
        entrypoint="example:transfer",
        function_id="transfer",
        mapping_id="transfer_source-values",
        entity_id="target",
        dataset_id="target",
        input_features=["input_value"],
        output_features=["result"],
    )
    plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        resources={},
        invocations=[invocation],
        stages=[["transfer"]],
    )
    context = data_lineage.build_context(definition, plan)
    step = context["stages"][0][0]
    source = step.input_tables[0]
    assert step.action == "Transfer Source Values"
    assert source.dataset == "source"
    assert [key.name for key in source.keys] == source_dimensions
    assert source.join_dimensions == ["id"]
    document = data_lineage.SECTION.render_page(
        data_lineage.SECTION.pages[0], render.WebsiteContext(), context
    )
    assert '<span class="context-link-label">Transfer Source Values</span>' in document
    assert f'<span class="context-link-icon" title="{kind.title()}"><i data-lucide=' in document
    assert '<h3 id="step-1-title">Transfer Source Values</h3>' in document
    assert '<p class="data-lineage-step-dataset">Dataset: target</p>' in document
    assert "Illustrative rows" not in document
    assert ">Main table" not in document
    assert document.index('data-side="output"') < document.index('data-side="input"')
    assert "data-dimension-transfer" not in document
    assert "data-lineage-mapping" not in document
    assert "<caption>" not in document
    assert 'aria-label="Source input: source illustrative table"' in document
    for side, row_count, dimensions in (
        ("input", source_rows, source_dimensions),
        ("output", target_rows, target_dimensions),
    ):
        match = re.search(
            rf'<table class="data-lineage-table" data-side="{side}">(.*?)</table>',
            document,
            re.DOTALL,
        )
        assert match is not None
        table = match.group(1)
        assert len(re.findall(r"<tr>", table)) - 1 == row_count
        assert 'data-column="id" data-join-key' in table
        assert 'data-column="time" data-join-key' not in table
        for dimension in dimensions:
            assert f'data-column="{dimension}"' in table
        change = {"input": "removed", "output": "added"}[side]
        assert ('data-column="time" data-dimension-change="' + change) in table or (
            "time" not in dimensions
        )
        assert 'data-column="id" data-dimension-change' not in table


class DataLineageStructureCollector(html_parser.HTMLParser):
    """Validate nesting and retain the parents of data-lineage layout elements."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str | None]]] = []
        self.parents: list[tuple[str, str | None]] = []
        self.columns: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "th" and "data-column" in attributes:
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


def test_main_table_accumulates_only_materialized_features(
    pump_bundle: project.BuildBundle,
) -> None:
    accumulated: dict[str | None, list[str]] = {}
    steps = [
        step
        for stage in data_lineage._build_stages(
            pump_bundle.spec_definition, pump_bundle.execution_plan
        )
        for step in stage
    ]
    for step in steps:
        expected = accumulated.setdefault(step.dataset, [])
        current_outputs = [
            column.name
            for column in step.columns
            if column.role == "Output" and step.function_kind != "escape"
        ]
        expected[:] = [name for name in expected if name not in current_outputs]
        expected.extend(current_outputs)
        assert [column.name for column in step.main_columns] == expected
        assert [column.name for column in step.main_columns if column.role == "Output"] == (
            current_outputs
        )
        for source in step.input_tables:
            assert source.dataset != step.dataset
        if step.function_kind == "vectorize":
            local_inputs = {column.name for column in step.columns if column.role == "Input"} & set(
                expected
            )
            assert {
                column.name for column in step.main_columns if column.role == "Input"
            } == local_inputs - set(current_outputs)


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
    ] == []


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
        assert step.action == invocation.mapping_id.replace("_", " ").replace("-", " ").title()
        assert step.dependencies == sorted(
            numbers[identifier] for identifier in invocation.dependency_ids
        )
        assert [column.name for column in step.columns if column.role == "Dimension"] == dimensions
        for role, features in (
            ("Input", invocation.input_features),
            ("Output", invocation.output_features),
        ):
            if invocation.function_kind == "escape":
                role = "Declared input" if role == "Input" else "Output"
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
                if column.role == "Output":
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
    assert "data-lineage-schema" not in document
    assert 'aria-label="Execution sections"' in document
    assert 'aria-label="Plan sections"' in document
    assert "Execution plan" not in document
    assert 'id="data-lineage-edges"' not in document
    assert "Follow each invocation's declared inputs and outputs." not in document
    assert "Illustration only:" not in document
    assert "data-lineage-status" not in document
    assert "No declared producer" not in document
    assert "Consumes the accumulated table" not in document
    assert "The read invocation supplies" not in document
    for column_type, icon in (
        ("float", "hash"),
        ("string", "case-sensitive"),
        ("datetime", "calendar-clock"),
    ):
        assert (
            f'<i data-lucide="{icon}" class="data-lineage-type-icon" data-type="{column_type}"'
            in document
        )
    assert '<span class="sr-only"> (float)</span>' in document
    assert '<span class="data-lineage-cell">1.23</span>' in document
    assert '<span class="data-lineage-cell">2024-01-01 01:00</span>' in document
    assert '<span class="data-lineage-cell">pu-1</span>' in document
    assert '<span class="data-lineage-cell">{}</span>' in document
    assert '<span class="data-lineage-cell">pl-1</span>' in document
    assert "Key 1" not in document


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
    script = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((tmp_path / "js").glob("data_lineage*.js"))
        + sorted((tmp_path / "js/data_lineage").glob("*.js"))
    )
    assert 'aria-label="Lineage playback" hidden' in document
    assert '<script type="module" src="../js/data_lineage.js"></script>' in document
    assert 'id="data-lineage-previous">Previous</button>' in document
    assert 'id="data-lineage-play" aria-pressed="false">Play</button>' in document
    assert 'id="data-lineage-next">Next</button>' in document
    panel = re.search(r'<aside class="site-context".*?</aside>', document, re.DOTALL)
    assert panel is not None
    assert 'id="data-lineage-toolbar"' in panel.group()
    assert "data-lineage-playback-progress" not in document
    assert panel.group().count("data-animation-step=") == len(
        pump_bundle.execution_plan.invocations
    )
    assert 'class="context-group-label animation-stage-label"><span>Stage 1</span>' in panel.group()
    assert "data-stage-marker" not in document
    assert "data-step-marker" not in document
    assert '.animation-steps a[aria-current="step"] { color: #fff; background: #1e293b;' in styles
    assert "box-shadow: inset 3px 0 var(--color-accent)" in styles
    assert 'link.setAttribute("aria-current", "step")' in script
    assert 'class="data-lineage-kicker"' not in document
    assert "Stage {{ stage_number }} / Step {{ step.number }}" not in document
    assert '<select id="animation-dataset" required>' in document
    assert "Choose a dataset</option>" in document
    assert 'title="pump_telemetry_dataset">Pump Telemetry Dataset</option>' in document
    dataset_groups = re.findall(
        r'<div class="context-link-group" data-animation-dataset="\d+">(.*?)</div>',
        panel.group(),
        re.DOTALL,
    )
    expected_datasets = {
        step.dataset
        for stage in data_lineage._build_stages(spec_definition, pump_bundle.execution_plan)
        for step in stage
    }
    assert len(dataset_groups) == len(expected_datasets)
    for group in dataset_groups:
        step_numbers = re.findall(r'<span class="animation-step-number">(\d+)</span>', group)
        assert step_numbers == [str(number) for number in range(1, len(step_numbers) + 1)]
    assert "grid-template-columns: minmax(0, 1fr);" in styles
    assert "minmax(0, 2fr) auto minmax(0, 3fr)" not in styles
    assert 'class="data-lineage-arrow" data-flow="up">' in document
    assert ".data-lineage-table-scroll { overflow-x: auto; overflow-y: hidden;" in styles
    assert ".data-lineage-step { margin: 20px 0; }" in styles
    assert ".data-lineage-table-scroll { overflow-x: auto; overflow-y: hidden; }" in styles
    assert "&uarr;" not in document
    assert '<span class="data-lineage-edge" aria-hidden="true"></span>' in document
    assert (
        '<span class="data-lineage-node icon--functions" aria-hidden="true">'
        '<i data-lucide="combine" class="site-icon"></i></span>' in document
    )
    assert "<code>aggregate</code>" in document
    assert "@keyframes data-lineage-flow-up" in styles
    assert ".data-lineage-edge { position: absolute; top: 0; bottom: 0;" in styles
    assert "justify-content: center; gap: 16px 24px; }" in styles
    assert "row.hidden = byRow && !completed && !visibleRows.has(row);" in script
    assert "<strong>aggregate</strong>" not in document
    assert 'class="data-lineage-invocation-type">Aggregate</small>' in document
    assert "data-lineage-invocation-phase" not in document
    assert "data-lineage-function-kind-label" not in document
    assert 'class="data-lineage-step-dataset">Dataset:' in document
    assert 'class="data-lineage-dataset"' not in document
    assert ">Main table" not in document
    assert "Illustrative rows" not in document
    assert "Same-table calculation" not in document
    assert "Highlighted input columns produce new features" not in document
    assert "Declared schema and dependencies" not in document
    assert "<details open" not in document
    assert "data-lineage-inspector" not in document
    assert "data-lineage-direction" not in document
    assert "data-lineage-zoom" not in document
    assert "data-lineage-animate" not in document
    assert '<table class="data-lineage-table" data-side="input">' in document
    assert '<table class="data-lineage-table" data-side="output">' in document
    assert "prefers-reduced-motion: reduce" in script
    assert "reducedMotion.addEventListener" in script
    assert '<span class="data-lineage-cell">' in document
    assert '[data-role="Existing"] .data-lineage-cell' in styles
    assert ".data-lineage-table [data-anchor] { position: sticky;" in styles
    assert ".data-lineage-minimap-view" in styles
    assert ".data-lineage-minimap > [data-role" not in styles
    assert "function buildMinimap" not in script
    assert "data-lineage-status" not in script + styles
    assert 'minimap.className = "data-lineage-minimap"' in script
    assert 'minimap.setAttribute("role", "scrollbar")' in script
    assert "function buildLinks(step)" in script
    assert 'svgElement("svg", { class: "data-lineage-links"' in script
    assert "thead th[data-join-key]" in script
    assert ".data-lineage-links .is-offscreen > path" in styles
    for kind in ("join", "input", "output"):
        assert f'addLink(layer, "{kind}"' in script
    assert 'marker-end": `url(#${step.id}-output-head)`' in script
    assert "function nodePoint(node, origin, toward)" in script
    assert ".data-lineage-arrow[data-feature-links] .data-lineage-edge { display: none; }" in styles
    assert ".data-lineage-links .is-new > path" in styles
    assert "join-head" not in script + styles
    assert "data-lineage-join-flow" not in styles
    flow_rule = re.search(r"([^}]*)\{[^}]*animation: data-lineage-data-flow", styles)
    assert flow_rule is not None
    assert '[data-link="input"], [data-link="output"]' in flow_rule.group(1)
    assert '[data-link="join"]' not in flow_rule.group(1)
    assert 'path.addEventListener("animationend"' in script
    assert 'addLink(layer, "write"' in script
    assert '[data-link="write"]' in flow_rule.group(1)
    assert "box-shadow: inset 2px 0 var(--ring), inset -2px 0 var(--ring)" in styles
    for role in ("Input", "Output"):
        assert f'.data-lineage-table [data-role="{role}"] {{ --tint:' in styles
    assert '.data-lineage-table [data-role="Dimension"] {' not in styles
    assert "[data-dimension-change" not in styles
    join_rule = re.search(r"\.data-lineage-table \[data-join-key\] \{([^}]*)\}", styles)
    assert join_rule is not None
    assert "--tint: var(--lineage-join-tint)" in join_rule.group(1)
    assert "--ring: transparent" in join_rule.group(1)
    assert "--lineage-shared: #fbbf24" in styles
    active_rule = re.search(r"\.data-lineage-table \.data-lineage-input-active \{([^}]*)\}", styles)
    assert active_rule is not None
    assert "--ring:" in active_rule.group(1)
    assert "background" not in active_rule.group(1)
    assert "minimap.setPointerCapture(event.pointerId)" in script
    assert 'minimap.addEventListener("keydown"' in script
    assert "scrollbar-width: none" in styles
    assert ".data-lineage-table-scroll[data-more-right] { mask-image:" in styles
    assert "function followCamera(" in script
    assert "function anchorKeys(" in script
    assert "ANCHOR_MAX_SHARE" in script
    assert "function buildMainTable(" in script
    assert "MAX_COLUMN_FRAMES" in script
    assert "FOLD_MIN_RUN" in script
    assert "CAMERA_CUT_VIEWPORTS" in script
    assert ".data-lineage-fold {" in styles
    assert '.data-lineage-overflow [data-role="Input"] .data-lineage-cell' in styles
    assert 'document.addEventListener("visibilitychange"' in script
    assert "window.clearTimeout(timer)" in script
    assert 'type: "column"' in script
    assert 'type: "row"' in script
    assert 'type: "inputs"' in script
    assert 'type: "group"' in script
    assert 'type: "invocation"' in script
    assert 'type: "write"' in script
    assert ".is-playing .data-lineage-new { animation:" in styles
    assert "animation-play-state" not in styles
    assert 'step.classList.toggle("is-playing", playing)' in script
    assert "data-lineage-grouped" in styles


def test_visible_tables_preserve_accumulated_columns(
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
    expected = []
    for stage in stages:
        for step in stage:
            expected.extend(
                (column.name, column.role) for column in step.columns if column.role == "Dimension"
            )
            expected.extend(
                (column.name, column.role)
                for column in step.main_columns
                if column.role != "Existing"
            )
            for source in step.input_tables:
                expected.extend(
                    (column.name, column.role) for column in source.keys + source.columns
                )
    assert collector.columns == expected


def test_page_size_stays_linear_for_many_columns() -> None:
    step_count = 80
    names = [f"feature_{number:03d}" for number in range(step_count + 1)]
    definition = spec.Spec.model_validate(
        {
            "dimensions": {"id": {"type": "integer"}},
            "entities": {
                "machine": {
                    "name": "machine",
                    "dimensions": ["id"],
                    "datasets": {"telemetry": {"features": {n: {"type": "float"} for n in names}}},
                }
            },
        }
    )
    invocations = [
        execution_plan.Invocation(
            id=f"step_{number}",
            function_kind="read" if number == 0 else "vectorize",
            entrypoint="example:step",
            function_id=f"step_{number}",
            mapping_id=f"step_{number}",
            entity_id="machine",
            dataset_id="telemetry",
            input_features=[] if number == 0 else [names[number - 1]],
            output_features=[names[number]],
        )
        for number in range(step_count + 1)
    ]
    plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        resources={},
        invocations=invocations,
        stages=[[invocation.id] for invocation in invocations],
    )
    context = data_lineage.build_context(definition, plan)
    last_step = context["stages"][-1][0]
    assert len(last_step.main_columns) == step_count + 1
    document = data_lineage.SECTION.render_page(
        data_lineage.SECTION.pages[0], render.WebsiteContext(), context
    )
    assert 'data-role="Existing"' not in document
    assert document.count('<th scope="col"') == 2 + 3 * step_count


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
