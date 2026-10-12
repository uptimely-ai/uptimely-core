import json
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from uptimely.compile import Compiler
from uptimely.engine import Engine
from uptimely.plan import ExecutionPlan, Plan
from uptimely.row_context import ContextExtent, RowContext, duration_nanoseconds
from uptimely.spec import Specification
from uptimely.spec.json_spec.bindings import is_aggregation_entry
from uptimely.spec.json_spec.json_model import (
    Binding,
    Call,
    Feature,
    FeatureMapping,
    Sink,
    VectorizeFunction,
)
from uptimely.spec.python_spec import bind, dataset, dimension, feature, mapping, ref, row_context
from uptimely.spec.python_spec.bind import _argument_definition, _binding_value
from uptimely.spec.render import create_website_pages


def read_observations() -> pl.DataFrame:
    return pl.DataFrame({"id": [3, 1, 2], "temperature": [10, 20, 30]})


def _read() -> mapping.Read:
    return mapping.Read(
        bind=bind.bind(read_observations),
        features=[
            feature.Feature(id="id", type="integer"),
            feature.Feature(id="temperature", type="integer"),
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


def _specification(binding: bind.Bind, context: RowContext | None = None) -> Specification:
    return Specification.from_python(
        datasets=[
            dataset.Dataset(
                id="observations",
                order=[dataset.Order(dimension=ref.dimension("id"), direction="asc")],
                mappings=[
                    _read(),
                    mapping.Vectorize(
                        id="result",
                        bind=binding,
                        features=[feature.Feature(id="result")],
                        row_context=context,
                    ),
                ],
            )
        ],
        dimensions=[dimension.Dimension(id="id", type="integer")],
    )


def test_dataset_authoring_uses_mappings_for_all_operation_types() -> None:
    assert {
        "read",
        "conform",
        "expand",
        "collapse",
        "vectorize",
    }.isdisjoint(dataset.Dataset.__dataclass_fields__)


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
    assert duration_nanoseconds(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "8", "-8h", "+8h", "8H", "PT8H", "1mo", "8 h", "1h 30m", "1h2h", "1h!", "1e3s", "0.1ns"],
)
def test_invalid_fixed_durations_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        row_context.time("unchanged", before=text)


@pytest.mark.parametrize("factory", [row_context.rows, row_context.steps])
@pytest.mark.parametrize("value", [-1, 1.5, True, "8", None])
def test_count_extents_require_nonnegative_integers(factory, value: object) -> None:
    with pytest.raises(ValidationError):
        factory("argument", before=value)


def test_annotations_preserve_values_and_primitive_schemas() -> None:
    argument = row_context.time(
        {"period": "8h", "counts": [row_context.rows(8, before=7)]},
        before="8h",
    )
    assert _binding_value(argument) == {"period": "8h", "counts": [8]}
    assert _argument_definition(argument) == {"type": "object"}
    assert _argument_definition(row_context.time("8h", before="8h")) == {"type": "string"}
    assert _argument_definition(row_context.rows(8, before=7)) == {"type": "integer"}


@pytest.mark.parametrize("factory", [row_context.time, row_context.steps, row_context.rows])
def test_helpers_return_row_context_bindings(factory) -> None:
    assert isinstance(factory("argument"), row_context.RowContextBinding)
    assert "RowContextBinding" in row_context.__all__
    assert not hasattr(row_context, "ContextBinding")


def test_feature_consolidates_directional_maxima() -> None:
    binding = bind.bind(
        calculate,
        column=ref.feature("temperature"),
        window=row_context.time("8h", before="8h", after="1h"),
        count=8,
        configuration={
            "period": row_context.time("8h", before="500m"),
            "counts": [row_context.time(8, before="3h", after="2h")],
        },
    )
    declaration = mapping.Vectorize(
        id="result",
        bind=binding,
        features=[feature.Feature(id="result")],
    )
    assert declaration.row_context.to_dict() == {
        "extent": "bounded",
        "before": {"time": "500m"},
        "after": {"time": "2h"},
    }
    model_mapping = declaration.to_model()
    assert model_mapping.binding.args["configuration"] == {"period": "8h", "counts": [8]}
    model_feature = (
        dataset.Dataset(id="observations", mappings=[declaration]).to_model().features["result"]
    )
    assert model_feature.row_context == declaration.row_context


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (row_context.time("8h", before="8h"), row_context.rows(8, before=7)),
        (row_context.rows(8, before=7), row_context.steps(8, after=2)),
        (row_context.steps(8), row_context.time("8h")),
        (row_context.time("8h", before=row_context.UNBOUNDED), row_context.rows(8)),
    ],
)
def test_feature_rejects_mixed_annotation_measurements(left, right) -> None:
    with pytest.raises(ValueError, match="one measurement"):
        mapping.Vectorize(
            id="result",
            bind=bind.bind(calculate, configuration={"first": left, "nested": [right]}),
        )


def test_feature_rejects_mixed_direct_context_and_annotation() -> None:
    with pytest.raises(ValueError, match="one measurement"):
        mapping.Vectorize(
            id="result",
            row_context=RowContext(after=ContextExtent(rows=1)),
            bind=bind.bind(calculate, window=row_context.time("8h", before="8h")),
        )


@pytest.mark.parametrize(
    ("measure", "before", "after"),
    [("time", "8h", "2h"), ("rows", 8, 2), ("steps", 8, 2)],
)
def test_same_measurement_round_trip_and_merge(measure, before, after) -> None:
    context = RowContext(
        before=ContextExtent.model_validate({measure: before}),
        after=ContextExtent.model_validate({measure: after}),
    )
    assert RowContext.model_validate(context.to_dict()) == context
    assert row_context.current().merge(context) == context
    assert context.merge(row_context.current()) == context
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
    plan = Compiler(
        _specification(bind.bind(calculate, column=ref.feature("temperature")))
    ).compile()
    payload = plan.plan.to_dict()
    operation = next(item for item in payload["operations"] if item["kind"] == kind)
    operation["row_context"] = context
    with pytest.raises(ValueError, match=message):
        Plan.from_dict(payload)


def test_specification_rejects_mixed_measurements(tmp_path: Path) -> None:
    specification = _specification(bind.bind(calculate, column=ref.feature("temperature")))
    path = tmp_path / "spec.json"
    specification.to_json(path)
    payload = json.loads(path.read_text())
    calculation = payload["entities"]["entity"]["datasets"][0]["features"]["result"]
    calculation["row_context"] = {"before": {"time": "8h", "rows": 10}}
    path.write_text(json.dumps(payload))
    with pytest.raises(ValidationError, match="one measurement"):
        Specification.from_json(path)


@pytest.mark.parametrize(
    "context", [RowContext(before=ContextExtent(rows=10)), row_context.rows(10, before=10)]
)
def test_explicit_context_is_merged_with_annotations(context) -> None:
    declaration = mapping.Vectorize(
        id="result",
        row_context=context,
        bind=bind.bind(calculate, window=row_context.rows("8h", before=7)),
        features=[feature.Feature(id="result")],
    )
    model_feature = (
        dataset.Dataset(id="observations", mappings=[declaration]).to_model().features["result"]
    )
    assert model_feature.row_context.before.rows == 10


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (row_context.rows(1, before=1), {"rows": 1}),
        (row_context.steps(1, before=1), {"steps": 1}),
        (row_context.time("8h", before="8h"), {"time": "8h"}),
    ],
)
def test_helpers_work_as_direct_feature_context(annotation, expected) -> None:
    declaration = mapping.Vectorize(
        id="result",
        bind=bind.bind(calculate, column=ref.feature("temperature")),
        row_context=annotation,
        features=[feature.Feature(id="result")],
    )
    model_dataset = dataset.Dataset(id="observations", mappings=[declaration]).to_model()
    model_mapping = model_dataset.mappings["result"]
    assert (
        model_dataset.features["result"].row_context.before.model_dump(exclude_none=True)
        == expected
    )
    assert model_mapping.binding.args == {"column": "$features.temperature"}


def test_direct_binding_declarations_collect_context() -> None:
    argument = row_context.rows(8, before=7)
    binding = bind.Bind(calculate, {"count": argument})
    assert not hasattr(binding, "row_context")
    assert mapping.Vectorize(id="result", bind=binding).row_context == argument.row_context


def test_mapping_model_does_not_own_feature_context() -> None:
    assert "row_context" not in FeatureMapping.model_fields
    with pytest.raises(ValidationError, match="row_context"):
        FeatureMapping(
            id="summary",
            binding=Binding(function="calculate"),
            features=["maximum"],
            row_context={"before": {"rows": 7}},
        )


def test_unbounded_is_explicit_and_dominates_bounded_values() -> None:
    binding = bind.bind(
        calculate,
        window=row_context.rows("unbounded preceding", before=row_context.UNBOUNDED),
        count=row_context.rows(8, before=7, after=2),
    )
    declaration = mapping.Vectorize(id="result", bind=binding)
    assert declaration.row_context.before.rows == "unbounded"
    assert declaration.row_context.after.rows == 2
    restored = RowContext.model_validate(declaration.row_context.to_dict())
    assert restored == declaration.row_context
    assert row_context.time(
        "native value", before=row_context.UNBOUNDED
    ).row_context.before.time == ("unbounded")


def test_unknown_current_partition_and_dataset_are_distinct() -> None:
    assert mapping.Vectorize(id="result", bind=bind.bind(calculate)).row_context is None
    current = row_context.current()
    assert current.to_dict() == {"extent": "bounded", "before": {}, "after": {}}
    assert RowContext.model_validate(current.to_dict()) == current
    assert row_context.partition().extent == "partition"
    assert row_context.dataset().extent == "dataset"
    bounded = row_context.rows(8, before=7).row_context
    assert bounded.merge(row_context.partition()) == row_context.partition()
    assert row_context.partition().merge(row_context.dataset()) == row_context.dataset()


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
    with pytest.raises(ValidationError):
        Feature(id="result", row_context=payload)


@pytest.mark.parametrize(
    ("model_type", "fields"),
    [
        (Binding, {"function": "calculate"}),
        (Call, {"function": "calculate", "entity": "entity", "feature": "result"}),
        (FeatureMapping, {"id": "result", "binding": Binding(function="calculate")}),
        (Sink, {"id": "result", "binding": Binding(function="calculate")}),
    ],
)
def test_non_vectorized_models_reject_context(model_type, fields: dict) -> None:
    assert "row_context" not in model_type.model_fields
    with pytest.raises(ValidationError, match="row_context"):
        model_type(**fields, row_context={})


def test_features_have_no_context_field() -> None:
    assert "row_context" not in feature.Feature.__dataclass_fields__
    with pytest.raises(TypeError, match="row_context"):
        feature.Feature(id="result", row_context=row_context.current())


@pytest.mark.parametrize("constructor", [mapping.aggregation, mapping.Aggregation])
def test_aggregation_unwraps_annotations_without_registering_context(constructor) -> None:
    args = {"configuration": {"windows": [row_context.time("8h", before="8h")]}}
    aggregation = (
        constructor(calculate, args)
        if constructor is mapping.Aggregation
        else constructor(calculate, **args)
    )
    entry = _binding_value({"items": [aggregation]})["items"][0]
    assert entry == {
        "function": "calculate",
        "args": {"configuration": {"windows": ["8h"]}},
    }
    assert "row_context" not in mapping.Aggregation.__dataclass_fields__
    assert is_aggregation_entry(entry)
    assert not is_aggregation_entry({**entry, "row_context": {}})
    collapse = mapping.Collapse(
        bind=bind.bind(calculate, aggregations={"result": aggregation})
    ).to_model()
    assert not hasattr(collapse, "row_context")


def test_shared_binding_supports_distinct_feature_contexts() -> None:
    shared = bind.bind(
        calculate,
        column=ref.feature("temperature"),
        window=row_context.time("8h", before="8h"),
    )
    first = mapping.Vectorize(
        id="first",
        bind=shared,
        features=[feature.Feature(id="first")],
    )
    second = mapping.Vectorize(
        id="second",
        bind=shared,
        features=[feature.Feature(id="second")],
        row_context=RowContext(before=ContextExtent(time="12h")),
    )
    baseline = _specification(shared)
    declaration = dataset.Dataset(
        id="observations",
        mappings=[
            _read(),
            first,
            second,
        ],
    )
    specification = Specification.from_python(
        datasets=[declaration],
        dimensions=[dimension.Dimension(id="id", type="integer")],
    )
    contexts = {
        operation.output: operation.row_context.before.time
        for operation in Compiler(specification).compile().operations
        if operation.kind == "vectorize"
    }
    assert contexts == {"first": "8h", "second": "12h"}
    assert not hasattr(shared, "row_context")
    # Compilation uses the feature's current metadata, not a stale derived call.
    calculation = baseline.entities["entity"].datasets[0].features["result"]
    calculation.row_context = RowContext(before=ContextExtent(time="16h"))
    operation = next(
        item for item in Compiler(baseline).compile().operations if item.kind == "vectorize"
    )
    assert operation.row_context.before.time == "16h"


@pytest.mark.parametrize(
    "operation_type",
    [mapping.Read, mapping.Conform, mapping.Expand, mapping.Collapse],
)
def test_mappings_unwrap_annotations_without_context(operation_type) -> None:
    declaration = operation_type(
        bind=bind.bind(calculate, configuration={"windows": [row_context.time("8h", before="8h")]})
    )
    model = declaration.to_model()
    assert "row_context" not in operation_type.__dataclass_fields__
    assert "row_context" not in FeatureMapping.model_fields
    assert "row_context" not in model.model_dump()
    assert model.binding.args == {"configuration": {"windows": ["8h"]}}
    assert "row_context" not in model.binding.model_dump()
    copied = dataset.Dataset(id="observations", mappings=[declaration]).to_model()
    assert "row_context" not in next(iter(copied.mappings.values())).model_dump()
    with pytest.raises(TypeError, match="row_context"):
        operation_type(bind=bind.bind(calculate), row_context=row_context.rows(1, before=1))


def test_mapping_module_exposes_only_current_mapping_declarations() -> None:
    assert not hasattr(mapping, "_Operation")
    assert not hasattr(mapping, "Mapping")
    assert mapping.Aggregation
    assert mapping.Vectorize
    assert feature.Feature


def test_input_scope_is_removed_from_function_templates() -> None:
    with pytest.raises(ValidationError, match="input_scope"):
        VectorizeFunction(id="calculate", entrypoint="module:calculate", input_scope="window")
    assert "input_scope" not in VectorizeFunction.model_json_schema()["properties"]


def test_spec_plan_and_batch_execution_preserve_context_and_arguments(tmp_path: Path) -> None:
    specification = _specification(
        bind.bind(
            calculate,
            column=ref.feature("temperature"),
            window=row_context.time("8h", before="8h"),
            count=8,
        )
    )
    spec_path = tmp_path / "spec.json"
    specification.to_json(spec_path)
    restored_specification = Specification.from_json(spec_path)
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

    plan = Compiler(restored_specification).compile()
    operation = next(item for item in plan.operations if item.kind == "vectorize")
    assert operation.row_context == original_feature.row_context
    assert all(item.row_context is None for item in plan.operations if item.kind != "vectorize")
    assert operation.arguments == {"column": "temperature", "window": "8h", "count": 8}
    assert plan.plan.resources["datasets"]["observations"]["order"] == [
        {"dimension": "$dimensions.id", "direction": "asc"}
    ]
    plan_path = plan.export_json(tmp_path / "plan.json")
    restored_plan = ExecutionPlan.from_json(plan_path)
    assert restored_plan.plan == plan.plan
    result = Engine(restored_plan).execute()
    assert not result.failures
    frame = next(iter(result.datasets.values()))
    assert frame["result"].to_list() == [11, 21, 31]
    assert frame["id"].to_list() == [3, 1, 2]  # Metadata does not introduce batch sorting.

    html = specification.create_html(tmp_path / "spec.html").read_text(encoding="utf-8")
    assert "Row context:" in html
    assert json.dumps(original_feature.row_context.to_dict(), sort_keys=True) in html
    create_website_pages(specification, tmp_path)
    features_html = (tmp_path / "spec_features.html").read_text(encoding="utf-8")
    assert "result" in features_html
    assert "Row context:" not in features_html
    html = plan.export_html(tmp_path / "plan.html").read_text(encoding="utf-8")
    assert "Row context" in html


def test_old_plans_without_context_load_as_unknown() -> None:
    plan = Compiler(
        _specification(bind.bind(calculate, column=ref.feature("temperature")))
    ).compile()
    payload = plan.plan.to_dict()
    for operation in payload["operations"]:
        operation.pop("row_context")
    assert all(item.row_context is None for item in Plan.from_dict(payload).operations)


def test_plan_context_is_present_in_portable_operations() -> None:
    plan = Compiler(
        _specification(
            bind.bind(calculate, column=ref.feature("temperature")),
            context=row_context.current(),
        )
    ).compile()
    operation = next(item for item in plan.operations if item.output == "result")
    assert operation.row_context == row_context.current()


def test_aggregations_execute_without_row_context() -> None:
    from examples.example_1.functions.calculation import aggregate_by_dimension, maximum

    annotated = mapping.aggregation(
        maximum,
        feature=ref.feature("temperature"),
    )
    assert _argument_definition(annotated) == {"type": "aggregation"}
    specification = Specification.from_python(
        datasets=[
            dataset.Dataset(
                id="input",
                mappings=[_read()],
            ),
            dataset.Dataset(
                id="summary",
                mappings=[
                    mapping.Collapse(
                        bind=bind.bind(
                            aggregate_by_dimension,
                            dataset=ref.dataset("input"),
                            dimensions=[ref.dimension("id")],
                            aggregations={"temperature_max": annotated},
                        ),
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
    plan = Compiler(specification).compile()
    operation = next(item for item in plan.operations if item.kind == "collapse")
    assert operation.row_context is None
    entry = operation.arguments["aggregations"]["temperature_max"]
    assert set(entry) == {"function", "args"}
    assert entry["args"] == {"feature": "temperature"}
    output_dataset = specification.entities["entity"].datasets[1]
    output = output_dataset.mappings["aggregate_by_dimension"]
    assert output_dataset.features["temperature_max"].row_context is None
    payload = output.model_dump()
    assert "row_context" not in payload["binding"]
    assert "row_context" not in payload["aggregations"]["temperature_max"]
    restored = Plan.from_dict(json.loads(json.dumps(plan.plan.to_dict())))
    assert restored == plan.plan
    assert not Engine(ExecutionPlan(restored)).execute().failures
