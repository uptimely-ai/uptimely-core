import json
import pathlib

import polars as pl
import pydantic
import pytest
from examples.example_1.functions import calculation as calculation_module

from uptimely import compile, engine, spec
from uptimely import plan as uptimely_plan
from uptimely import row_context as row_context_module
from uptimely.spec import python_spec, render
from uptimely.spec.json_spec import json_model
from uptimely.spec.python_spec import bind, dataset, dimension, feature, row_context


def read_observations() -> pl.DataFrame:
    return pl.DataFrame({"id": [3, 1, 2], "temperature": [10, 20, 30]})


def _read() -> python_spec.mapping.Read:
    return python_spec.mapping.Read(
        bind=bind.bind(read_observations),
        features=[
            python_spec.feature.Feature(id="id", type="integer"),
            python_spec.feature.Feature(id="temperature", type="integer"),
        ],
    )


def calculate(
    column: str,
    window: str = "8h",
    count: int = 8,
    configuration: dict | None = None,
) -> pl.Expr:
    assert window == "8h"
    assert count == 8
    assert configuration is None or configuration == {"period": "8h", "counts": [8]}
    return pl.col(column) + 1


def _specification(
    binding: bind.Bind,
    context: row_context.RowContext | None = None,
) -> spec.Specification:
    return spec.Specification.from_python(
        datasets=[
            python_spec.dataset.Dataset(
                id="observations",
                order=[
                    python_spec.dataset.Order(
                        dimension=python_spec.ref.dimension("id"), direction="asc"
                    )
                ],
                mappings=[
                    _read(),
                    python_spec.mapping.Vectorize(
                        id="result",
                        bind=binding,
                        features=[python_spec.feature.Feature(id="result")],
                        row_context=context,
                    ),
                ],
            )
        ],
        dimensions=[python_spec.dimension.Dimension(id="id", type="integer")],
    )


def _aggregation_specification(aggregation: bind.Bind) -> spec.Specification:
    return spec.Specification.from_python(
        datasets=[
            dataset.Dataset(id="input", mappings=[_read()]),
            dataset.Dataset(
                id="summary",
                mappings=[
                    python_spec.mapping.Collapse(
                        id="summary",
                        bind=aggregation,
                        features=[
                            feature.Feature(id="id", type="integer"),
                            feature.Feature(id="temperature_max", type="integer"),
                        ],
                    )
                ],
            ),
        ],
        dimensions=[dimension.Dimension(id="id", type="integer")],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0s", 0),
        ("8h", 28_800_000_000_000),
        ("1h30m", 5_400_000_000_000),
        ("1.5s", 1_500_000_000),
        ("1ms2us3ns", 1_002_003),
        ("1d", 86_400_000_000_000),
        ("1w", 604_800_000_000_000),
        ("0.000000001s", 1),
        ("999999999999999999999999999999h", 999999999999999999999999999999 * 3_600_000_000_000),
    ],
)
def test_fixed_durations_are_exact(text: str, expected: int) -> None:
    assert row_context_module.duration_nanoseconds(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "8", "-8h", "+8h", "8H", "PT8H", "1mo", "8 h", "1h 30m", "1h2h", "1h!", "1e3s", "0.1ns"],
)
def test_invalid_fixed_durations_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        python_spec.row_context.time("unchanged", before=text)


@pytest.mark.parametrize(
    "factory",
    [python_spec.row_context.rows, python_spec.row_context.steps],
)
@pytest.mark.parametrize("value", [-1, 1.5, True, "8", None])
def test_count_extents_require_nonnegative_integers(factory, value: object) -> None:
    with pytest.raises(pydantic.ValidationError):
        factory("argument", before=value)


def test_annotations_preserve_values_and_primitive_schemas() -> None:
    argument = python_spec.row_context.time(
        {"period": "8h", "counts": [python_spec.row_context.rows(8, before=7)]},
        before="8h",
    )
    assert bind._binding_value(argument) == {
        "period": "8h",
        "counts": [8],
    }
    assert bind._argument_definition(argument) == {"type": "object"}
    assert bind._argument_definition(python_spec.row_context.time("8h", before="8h")) == {
        "type": "string"
    }
    assert bind._argument_definition(python_spec.row_context.rows(8, before=7)) == {
        "type": "integer"
    }


@pytest.mark.parametrize(
    "factory",
    [
        python_spec.row_context.time,
        python_spec.row_context.steps,
        python_spec.row_context.rows,
    ],
)
def test_helpers_return_row_context_bindings(factory) -> None:
    assert isinstance(factory("argument"), row_context.RowContextBinding)
    assert "RowContextBinding" in row_context.__all__


def test_feature_consolidates_directional_maxima() -> None:
    binding = bind.bind(
        calculate,
        column=python_spec.ref.feature("temperature"),
        window=python_spec.row_context.time("8h", before="8h", after="1h"),
        count=8,
        configuration={
            "period": python_spec.row_context.time("8h", before="500m"),
            "counts": [python_spec.row_context.time(8, before="3h", after="2h")],
        },
    )
    declaration = python_spec.mapping.Vectorize(
        id="result",
        bind=binding,
        features=[python_spec.feature.Feature(id="result")],
    )
    assert declaration.row_context.to_dict() == {
        "extent": "bounded",
        "before": {"time": "500m"},
        "after": {"time": "2h"},
    }
    model_mapping = declaration.to_model()
    assert model_mapping.binding.args["configuration"] == {"period": "8h", "counts": [8]}
    model_feature = (
        python_spec.dataset.Dataset(id="observations", mappings=[declaration])
        .to_model()
        .features["result"]
    )
    assert model_feature.row_context == declaration.row_context


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            python_spec.row_context.time("8h", before="8h"),
            python_spec.row_context.rows(8, before=7),
        ),
        (
            python_spec.row_context.rows(8, before=7),
            python_spec.row_context.steps(8, after=2),
        ),
        (
            python_spec.row_context.steps(8),
            python_spec.row_context.time("8h"),
        ),
        (
            python_spec.row_context.time("8h", before=python_spec.row_context.UNBOUNDED),
            python_spec.row_context.rows(8),
        ),
    ],
)
def test_feature_rejects_mixed_annotation_measurements(left, right) -> None:
    with pytest.raises(ValueError, match="one measurement"):
        python_spec.mapping.Vectorize(
            id="result",
            bind=bind.bind(calculate, configuration={"first": left, "nested": [right]}),
        )


def test_feature_rejects_mixed_direct_context_and_annotation() -> None:
    with pytest.raises(ValueError, match="one measurement"):
        python_spec.mapping.Vectorize(
            id="result",
            row_context=row_context.RowContext(after=row_context.ContextExtent(rows=1)),
            bind=bind.bind(calculate, window=python_spec.row_context.time("8h", before="8h")),
        )


@pytest.mark.parametrize(
    ("measure", "before", "after"),
    [("time", "8h", "2h"), ("rows", 8, 2), ("steps", 8, 2)],
)
def test_same_measurement_round_trip_and_merge(measure, before, after) -> None:
    context = row_context.RowContext(
        before=row_context.ContextExtent.model_validate({measure: before}),
        after=row_context.ContextExtent.model_validate({measure: after}),
    )
    assert row_context.RowContext.model_validate(context.to_dict()) == context
    assert python_spec.row_context.current().merge(context) == context
    assert context.merge(python_spec.row_context.current()) == context
    assert context.merge(context) == context


@pytest.mark.parametrize(
    ("kind", "context", "message"),
    [
        ("vectorize", {"before": {"time": "8h"}, "after": {"rows": 1}}, "one measurement"),
        ("vectorize", {"before": {"rows": -1}}, "greater than or equal"),
        ("read", {}, "Only vectorize operations"),
    ],
)
def test_plan_rejects_invalid_context(kind: str, context: dict, message: str) -> None:
    plan = compile.Compiler(
        _specification(bind.bind(calculate, column=python_spec.ref.feature("temperature")))
    ).compile()
    payload = plan.plan.to_dict()
    operation = next(item for item in payload["operations"] if item["kind"] == kind)
    operation["row_context"] = context
    with pytest.raises(ValueError, match=message):
        uptimely_plan.Plan.from_dict(payload)


def test_specification_rejects_mixed_measurements(tmp_path: pathlib.Path) -> None:
    specification = _specification(
        bind.bind(calculate, column=python_spec.ref.feature("temperature"))
    )
    path = tmp_path / "spec.json"
    specification.to_json(path)
    payload = json.loads(path.read_text())
    calculation = payload["entities"]["entity"]["datasets"][0]["features"]["result"]
    calculation["row_context"] = {"before": {"time": "8h", "rows": 10}}
    path.write_text(json.dumps(payload))
    with pytest.raises(pydantic.ValidationError, match="one measurement"):
        spec.Specification.from_json(path)


@pytest.mark.parametrize(
    "context",
    [
        row_context.RowContext(before=row_context.ContextExtent(rows=10)),
        python_spec.row_context.rows(10, before=10),
    ],
)
def test_explicit_context_is_merged_with_annotations(context) -> None:
    declaration = python_spec.mapping.Vectorize(
        id="result",
        row_context=context,
        bind=bind.bind(calculate, window=python_spec.row_context.rows("8h", before=7)),
        features=[python_spec.feature.Feature(id="result")],
    )
    model_feature = (
        python_spec.dataset.Dataset(id="observations", mappings=[declaration])
        .to_model()
        .features["result"]
    )
    assert model_feature.row_context.before.rows == 10


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (python_spec.row_context.rows(1, before=1), {"rows": 1}),
        (python_spec.row_context.steps(1, before=1), {"steps": 1}),
        (python_spec.row_context.time("8h", before="8h"), {"time": "8h"}),
    ],
)
def test_helpers_work_as_direct_feature_context(annotation, expected) -> None:
    declaration = python_spec.mapping.Vectorize(
        id="result",
        bind=bind.bind(calculate, column=python_spec.ref.feature("temperature")),
        row_context=annotation,
        features=[python_spec.feature.Feature(id="result")],
    )
    model_dataset = python_spec.dataset.Dataset(
        id="observations", mappings=[declaration]
    ).to_model()
    model_mapping = model_dataset.mappings["result"]
    assert (
        model_dataset.features["result"].row_context.before.model_dump(exclude_none=True)
        == expected
    )
    assert model_mapping.binding.args == {"column": "$features.temperature"}


def test_direct_binding_declarations_collect_context() -> None:
    argument = python_spec.row_context.rows(8, before=7)
    binding = bind.Bind(calculate, {"count": argument})
    assert (
        python_spec.mapping.Vectorize(id="result", bind=binding).row_context == argument.row_context
    )


def test_unbounded_is_explicit_and_dominates_bounded_values() -> None:
    binding = bind.bind(
        calculate,
        window=python_spec.row_context.rows(
            "unbounded preceding", before=python_spec.row_context.UNBOUNDED
        ),
        count=python_spec.row_context.rows(8, before=7, after=2),
    )
    declaration = python_spec.mapping.Vectorize(id="result", bind=binding)
    assert declaration.row_context.before.rows == "unbounded"
    assert declaration.row_context.after.rows == 2
    restored = row_context.RowContext.model_validate(declaration.row_context.to_dict())
    assert restored == declaration.row_context
    assert python_spec.row_context.time(
        "native value", before=python_spec.row_context.UNBOUNDED
    ).row_context.before.time == ("unbounded")


def test_unknown_current_partition_and_dataset_are_distinct() -> None:
    assert python_spec.mapping.Vectorize(id="result", bind=bind.bind(calculate)).row_context is None
    current = python_spec.row_context.current()
    assert current.to_dict() == {"extent": "bounded", "before": {}, "after": {}}
    assert row_context.RowContext.model_validate(current.to_dict()) == current
    assert python_spec.row_context.partition().extent == "partition"
    assert python_spec.row_context.dataset().extent == "dataset"
    bounded = python_spec.row_context.rows(8, before=7).row_context
    assert bounded.merge(python_spec.row_context.partition()) == python_spec.row_context.partition()
    assert (
        python_spec.row_context.partition().merge(python_spec.row_context.dataset())
        == python_spec.row_context.dataset()
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"before": None},
        {"before": {"rows": None}},
        {"after": {"time": None}},
        {"before": {"rows": -1}},
        {"before": {"time": "1month"}},
        {"before": {"unknown": 2}},
        {"extent": "unknown"},
        {"extent": "partition", "before": {"rows": 1}},
        {"extent": "dataset", "after": {"time": "0s"}},
        {"before": {"time": "8h", "rows": 10}},
        {"before": {"rows": 10}, "after": {"time": "8h"}},
        {"before": {"steps": 0}, "after": {"rows": 0}},
        {"before": {"time": "unbounded"}, "after": {"rows": 1}},
    ],
)
def test_canonical_context_rejects_invalid_metadata(payload: dict) -> None:
    with pytest.raises(pydantic.ValidationError):
        json_model.Feature(id="result", row_context=payload)


@pytest.mark.parametrize(
    ("model_type", "fields"),
    [
        (json_model.Binding, {"function": "calculate"}),
        (
            json_model.Call,
            {"function": "calculate", "entity": "entity", "feature": "result"},
        ),
        (
            json_model.FeatureMapping,
            {
                "id": "result",
                "binding": json_model.Binding(function="calculate"),
            },
        ),
    ],
)
def test_non_vectorized_models_reject_context(model_type, fields: dict) -> None:
    with pytest.raises(pydantic.ValidationError, match="row_context"):
        model_type(**fields, row_context={})


def test_shared_binding_supports_distinct_feature_contexts() -> None:
    shared = bind.bind(
        calculate,
        column=python_spec.ref.feature("temperature"),
        window=python_spec.row_context.time("8h", before="8h"),
    )
    first = python_spec.mapping.Vectorize(
        id="first",
        bind=shared,
        features=[python_spec.feature.Feature(id="first")],
    )
    second = python_spec.mapping.Vectorize(
        id="second",
        bind=shared,
        features=[python_spec.feature.Feature(id="second")],
        row_context=row_context.RowContext(before=row_context.ContextExtent(time="12h")),
    )
    baseline = _specification(shared)
    declaration = python_spec.dataset.Dataset(
        id="observations",
        mappings=[
            _read(),
            first,
            second,
        ],
    )
    specification = spec.Specification.from_python(
        datasets=[declaration],
        dimensions=[python_spec.dimension.Dimension(id="id", type="integer")],
    )
    contexts = {
        operation.output: operation.row_context.before.time
        for operation in compile.Compiler(specification).compile().operations
        if operation.kind == "vectorize"
    }
    assert contexts == {"first": "8h", "second": "12h"}
    # Compilation uses the feature's current metadata, not a stale derived call.
    calculation = baseline.entities["entity"].datasets[0].features["result"]
    calculation.row_context = row_context.RowContext(before=row_context.ContextExtent(time="16h"))
    operation = next(
        item for item in compile.Compiler(baseline).compile().operations if item.kind == "vectorize"
    )
    assert operation.row_context.before.time == "16h"


@pytest.mark.parametrize(
    "operation_type",
    [python_spec.mapping.Read, python_spec.mapping.Conform, python_spec.mapping.Expand],
)
def test_mappings_unwrap_row_context_annotations_from_arguments(operation_type) -> None:
    declaration = operation_type(
        bind=bind.bind(
            calculate,
            configuration={"windows": [python_spec.row_context.time("8h", before="8h")]},
        )
    )
    model = declaration.to_model()
    assert model.binding.args == {"configuration": {"windows": ["8h"]}}
    copied = dataset.Dataset(id="observations", mappings=[declaration]).to_model()
    assert next(iter(copied.mappings.values())).binding.args == {
        "configuration": {"windows": ["8h"]}
    }


def test_spec_plan_and_batch_execution_preserve_context_and_arguments(
    tmp_path: pathlib.Path,
) -> None:
    specification = _specification(
        bind.bind(
            calculate,
            column=python_spec.ref.feature("temperature"),
            window=python_spec.row_context.time("8h", before="8h"),
            count=8,
        )
    )
    spec_path = tmp_path / "spec.json"
    specification.to_json(spec_path)
    restored_specification = spec.Specification.from_json(spec_path)
    original_feature = specification.entities["entity"].datasets[0].features["result"]
    restored_feature = restored_specification.entities["entity"].datasets[0].features["result"]
    assert restored_feature.row_context == original_feature.row_context
    assert (
        "row_context"
        not in specification.entities["entity"].datasets[0].mappings["result"].binding.model_dump()
    )
    assert "row_context" not in specification.calls[0].model_dump()
    exported = json.loads(spec_path.read_text())
    exported_feature = exported["entities"]["entity"]["datasets"][0]["features"]["result"]
    assert exported_feature["row_context"] == original_feature.row_context.to_dict()
    assert "binding" not in exported_feature
    assert (
        "row_context"
        not in exported["entities"]["entity"]["datasets"][0]["mappings"]["result"]["binding"]
    )
    assert specification.functions.vectorize["calculate"].args["window"].type == "string"

    plan = compile.Compiler(restored_specification).compile()
    operation = next(item for item in plan.operations if item.kind == "vectorize")
    assert operation.row_context == original_feature.row_context
    assert all(item.row_context is None for item in plan.operations if item.kind != "vectorize")
    assert operation.arguments == {"column": "temperature", "window": "8h", "count": 8}
    assert plan.plan.resources["datasets"]["observations"]["order"] == [
        {"dimension": "$dimensions.id", "direction": "asc"}
    ]
    plan_path = plan.export_json(tmp_path / "plan.json")
    restored_plan = uptimely_plan.ExecutionPlan.from_json(plan_path)
    assert restored_plan.plan == plan.plan
    result = engine.Engine(restored_plan).execute()
    assert not result.failures
    frame = next(iter(result.datasets.values()))
    assert frame["result"].to_list() == [11, 21, 31]
    assert frame["id"].to_list() == [3, 1, 2]  # Metadata does not introduce batch sorting.

    html = specification.create_html(tmp_path / "spec.html").read_text(encoding="utf-8")
    assert "Row context:" in html
    assert json.dumps(original_feature.row_context.to_dict(), sort_keys=True) in html
    render.create_website_pages(specification, tmp_path)
    features_html = (tmp_path / "features.html").read_text(encoding="utf-8")
    assert "result" in features_html
    assert "Row context:" not in features_html
    html = plan.export_html(tmp_path / "plan.html").read_text(encoding="utf-8")
    assert "Row context" in html


def test_plan_context_is_present_in_portable_operations() -> None:
    plan = compile.Compiler(
        _specification(
            bind.bind(calculate, column=python_spec.ref.feature("temperature")),
            context=python_spec.row_context.current(),
        )
    ).compile()
    operation = next(item for item in plan.operations if item.output == "result")
    assert operation.row_context == python_spec.row_context.current()


def test_collapse_functions_execute_without_row_context() -> None:
    annotated = bind.bind(
        calculation_module.maximum,
        feature=python_spec.ref.feature("temperature"),
    )
    specification = _aggregation_specification(annotated)
    plan = compile.Compiler(specification).compile()
    operation = next(item for item in plan.operations if item.kind == "collapse")
    assert operation.row_context is None
    assert operation.entrypoint.endswith(":maximum")
    assert operation.arguments == {"feature": "temperature"}
    output_dataset = specification.entities["entity"].datasets[1]
    output = output_dataset.mappings["summary"]
    assert output_dataset.features["temperature_max"].row_context is None
    payload = output.model_dump()
    assert "group_by" not in payload
    assert "row_context" not in payload["binding"]
    restored = uptimely_plan.Plan.from_dict(json.loads(json.dumps(plan.plan.to_dict())))
    assert restored == plan.plan
    assert not engine.Engine(uptimely_plan.ExecutionPlan(restored)).execute().failures
