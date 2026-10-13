"""Tests for processing tables and producer colors in the documentation website."""

import pathlib
import re

from uptimely import compile, spec
from uptimely.docs import docs, lineage

SPEC_PATH = pathlib.Path("examples/example_1/_generated/spec/spec.json")


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
        dimensions = specification.entities[operation.entity_id].dimensions
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
    assert document.count('<table class="lineage-table">') == len(plan.operations)
    assert 'aria-label="Execution sections"' in document
    assert 'aria-label="Plan sections"' in document
    assert "Execution plan" not in document
    assert 'id="lineage-edges"' in document
    assert 'path.setAttribute("marker-end"' in document
    assert 'const edgeColor = "#94a3b8";' in document
    assert 'arrow.setAttribute("fill", edgeColor);' in document
    assert 'path.setAttribute("stroke", edgeColor);' in document
    assert 'path.setAttribute("marker-end", "url(#lineage-arrow)");' in document
    assert 'source.style.getPropertyValue("--step-color")' not in document
    assert "new ResizeObserver(updateView)" in document
    assert "Tables show declared column types, not runtime values" in document
    assert "Write boundary:" in document
    assert "No declared producer" not in document


def test_empty_lineage_has_explicit_empty_state(tmp_path: pathlib.Path) -> None:
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert "No processing steps." in document
    assert '<table class="lineage-table">' not in document
    assert 'href="../execution/data_lineage.html" aria-current="page"' in document


def test_lineage_has_no_legend_badges(tmp_path: pathlib.Path) -> None:
    docs.create_html(spec.Specification(), tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert "lineage-legend" not in document
    assert "Data lineage color key" not in document


def test_lineage_has_compact_tables_and_zoom_controls(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert ".lineage-stage { position: relative; width: 320px;" in document
    assert "padding: 5px 6px;" in document
    assert 'aria-label="Data lineage zoom" hidden' in document
    assert 'aria-label="Zoom out"' in document
    assert 'aria-label="Zoom in"' in document
    assert 'id="lineage-fit">Fit view</button>' in document
    assert 'id="lineage-reset">100%</button>' in document
    assert "let zoom = 0.75;" in document
    assert "board.style.transform = `scale(${zoom})`;" in document
    assert "canvas.style.width = `${board.offsetWidth * zoom}px`;" in document
    assert "canvas.style.height = `${board.offsetHeight * zoom}px`;" in document
    assert "(viewport.clientWidth - 24) / board.offsetWidth" in document
    assert "(viewport.clientHeight - 24) / board.offsetHeight" in document
    assert "(sourceBounds.right - bounds.left) / zoom" in document
    assert "(targetBounds.left - bounds.left) / zoom" in document
    assert document.count("<summary>Dataset details</summary>") == len(
        compile.Compiler(specification).compile().operations
    )
    assert "<details open" not in document


def test_lineage_escapes_declared_row_scope(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    dataset = next(iter(specification.entities.values())).datasets[0]
    dataset.row_scope.grain = "<script>alert('grain')</script>"
    docs.create_html(specification, tmp_path / "index.html")
    document = (tmp_path / "execution/data_lineage.html").read_text(encoding="utf-8")
    assert dataset.row_scope.grain not in document
    assert "&lt;script&gt;alert(&#39;grain&#39;)&lt;/script&gt;" in document
