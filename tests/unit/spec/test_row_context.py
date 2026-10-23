import datetime
import json
import pathlib

import polars as pl
import pydantic
import pytest
from conftest import engine_for_plan, render_explorer

from uptimely import compiler, row_context, spec
from uptimely.compiler import plan as uptimely_plan
from uptimely.spec.python import bind, dataset, dimension, entity, feature, mapping, ref
from uptimely.spec.python import row_context as authoring


def read_observations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [datetime.datetime(2026, 1, 2), datetime.datetime(2026, 1, 1)],
            "temperature": [10, 20],
        }
    )


def calculate(dataset: pl.DataFrame, column: str, output: str, configuration: dict) -> pl.DataFrame:
    assert configuration == {"windows": ["8h", "24h"]}
    return dataset.with_columns((pl.col(column) + 1).alias(output))


def maximum(dataset: pl.DataFrame, column: str, output: str) -> pl.DataFrame:
    """Return a whole-dataset maximum without observation-context requirements."""
    return dataset.select(pl.col(column).max().alias(output))


def _spec(context=None, *, ordered=True, dimension_type="datetime"):
    return spec.from_python(
        datasets=[
            dataset.Dataset(
                id="observations",
                order=[dataset.Order(ref.dimension("timestamp"), "asc")] if ordered else [],
                mappings=[
                    mapping.Mapping(
                        bind=bind.bind(ref.function(read_observations, operation="read")),
                        outputs=[
                            feature.Feature(id="timestamp", type=dimension_type),
                            feature.Feature(id="temperature", type="integer"),
                        ],
                    ),
                    mapping.Mapping(
                        id="result",
                        inputs=[ref.feature("temperature")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        row_context=context,
                        bind=bind.bind(
                            ref.function(calculate, operation="vectorize"),
                            dataset=ref.current_dataset().dataframe,
                            column=ref.feature("temperature").id,
                            output=ref.feature("result").id,
                            configuration={"windows": ["8h", "24h"]},
                        ),
                    ),
                ],
            )
        ],
        dimensions=[dimension.Dimension(id="timestamp", type=dimension_type)],
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
def test_fixed_durations_are_exact(text, expected):
    assert row_context.duration_nanoseconds(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "8",
        "-8h",
        "+8h",
        "8H",
        "PT8H",
        "1mo",
        "8 h",
        "1h 30m",
        "1h2h",
        "1h!",
        "1e3s",
        "0.1ns",
    ],
)
def test_invalid_fixed_durations_are_rejected(text):
    with pytest.raises(ValueError):
        authoring.time("unchanged", dimension=ref.dimension("timestamp"), before=text)


@pytest.mark.parametrize("factory", [authoring.rows, authoring.steps])
@pytest.mark.parametrize("value", [-1, 1.5, True, "8", None])
def test_count_extents_require_nonnegative_integers(factory, value):
    kwargs = {"dimension": ref.dimension("index")} if factory is authoring.steps else {}
    with pytest.raises(pydantic.ValidationError):
        factory("argument", before=value, **kwargs)


def test_mapping_consolidates_directional_maxima_and_unwraps_arguments():
    declaration = mapping.Mapping(
        bind=bind.bind(
            ref.function(calculate, operation="vectorize"),
            configuration={
                "windows": [
                    authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h"),
                    authoring.time(
                        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
                    ),
                ],
            },
        ),
        row_context=authoring.time("explicit", dimension=ref.dimension("timestamp"), after="3h"),
    )
    assert declaration.to_model().row_context.to_dict() == {
        "dimension": "$dimensions.timestamp",
        "before": {"time": "24h"},
        "after": {"time": "3h"},
    }
    assert declaration.to_model().binding.args == {"configuration": {"windows": ["8h", "24h"]}}
    assert bind._argument_definition(declaration.bind.args["configuration"]) == {
        "type": "object{str: array[string]}"
    }


def test_consolidation_rejects_different_dimensions_and_measurements():
    first = authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h")
    second = authoring.time("8h", dimension=ref.dimension("other"), before="8h")
    with pytest.raises(ValueError, match="one dimension"):
        mapping.Mapping(
            bind=bind.bind(
                ref.function(calculate, operation="vectorize"), configuration=[first, second]
            )
        )
    with pytest.raises(ValueError, match="one measurement"):
        mapping.Mapping(
            bind=bind.bind(
                ref.function(calculate, operation="vectorize"),
                configuration=[
                    first,
                    authoring.rows(8, before=7),
                ],
            )
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
        {"extent": "bounded"},
        {"partition_by": []},
        {"on": "clock"},
        {"before": {"time": "8h"}},
        {"before": {"steps": 1}},
        {"dimension": "$features.operating_hours", "before": {"steps": 100}},
        {"dimension": "$dimensions.timestamp", "before": {"rows": 1}},
        {"dimension": "$dimensions.timestamp", "before": {"time": "8h", "rows": 10}},
        {"dimension": "$dimensions.timestamp", "before": {"time": "8h"}, "after": {"steps": 1}},
    ],
)
def test_context_rejects_invalid_metadata(payload):
    with pytest.raises(pydantic.ValidationError):
        row_context.RowContext.model_validate(payload)


def test_unknown_current_and_whole_dataset_context_are_distinct():
    assert (
        mapping.Mapping(bind=bind.bind(ref.function(calculate, operation="vectorize"))).row_context
        is None
    )
    assert authoring.current().to_dict() == {"before": {}, "after": {}}
    whole = authoring.dataset()
    assert whole.to_dict() == {"before": "unbounded", "after": "unbounded"}
    assert not whole.requires_order
    assert whole.merge(authoring.rows(8, before=7)) == whole
    assert row_context.RowContext.model_validate(whole.to_dict()) == whole
    assert row_context.RowContext(before="unbounded").requires_order


def test_unbounded_dominates_bounded_directional_requirements():
    left = authoring.time(
        "native", dimension=ref.dimension("timestamp"), before=authoring.UNBOUNDED
    ).row_context
    right = authoring.time(
        "8h", dimension=ref.dimension("timestamp"), before="8h", after="2h"
    ).row_context
    merged = left.merge(right)
    assert merged.before.time == "unbounded"
    assert merged.after.time == "2h"


@pytest.mark.parametrize(
    ("context", "dimension_type", "message"),
    [
        (
            row_context.RowContext(
                dimension="$dimensions.other", before=row_context.ContextExtent(time="8h")
            ),
            "datetime",
            "not in the input entity",
        ),
        (
            row_context.RowContext(
                dimension="$dimensions.timestamp", before=row_context.ContextExtent(time="8h")
            ),
            "integer",
            "must have type datetime",
        ),
        (
            row_context.RowContext(
                dimension="$dimensions.timestamp", before=row_context.ContextExtent(steps=8)
            ),
            "datetime",
            "must have type integer",
        ),
    ],
)
def test_context_dimension_is_validated(context, dimension_type, message):
    with pytest.raises(ValueError, match=message):
        _spec(context, dimension_type=dimension_type)


def test_directional_context_requires_dataset_order():
    with pytest.raises(ValueError, match="requires dataset order"):
        _spec(authoring.rows(1, before=1).row_context, ordered=False)
    _spec(authoring.current(), ordered=False)
    _spec(authoring.dataset(), ordered=False)


def test_spec_plan_execution_and_explorer_preserve_context(tmp_path: pathlib.Path):
    context = authoring.time(
        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
    ).row_context
    spec_definition = _spec(context)
    path = tmp_path / "spec.json"
    spec.write_document(spec_definition, path)
    payload = json.loads(path.read_text())
    authored_dataset = payload["entities"]["entity"]["datasets"]["observations"]
    assert "row_context" not in authored_dataset["features"]["result"]
    assert authored_dataset["mappings"]["result"]["row_context"] == context.to_dict()
    restored = spec.load_spec(path)
    compiled = compiler.Compiler(restored).compile()
    operation = next(item for item in compiled.callables if item.operation == "vectorize")
    assert operation.input_features == ["temperature"]
    assert operation.row_context == context
    portable = uptimely_plan.ExecutionPlan(uptimely_plan.Plan.from_dict(compiled.to_dict()))
    result = engine_for_plan(portable).run()
    assert not result.failures
    frame = result.datasets["observations"]
    assert frame.sort("timestamp")["result"].to_list() == [21, 11]
    render_explorer(restored, tmp_path / "index.html")
    assert "Row context:" not in (tmp_path / "spec/features.html").read_text()
    assert "Row context" in (tmp_path / "plan/stages.html").read_text()


@pytest.mark.parametrize("operation", ["read", "expand", "collapse", "vectorize"])
def test_all_data_mappings_preserve_annotated_context(operation):
    declaration = mapping.Mapping(
        bind=bind.bind(
            ref.function(calculate, operation=operation),
            configuration={"windows": [authoring.rows(8, before=7)]},
        )
    )
    assert declaration.to_model().row_context.before.rows == 7
    assert declaration.to_model().binding.args == {"configuration": {"windows": [8]}}


def test_spec_plan_and_batch_execution_preserve_context_and_arguments(
    tmp_path: pathlib.Path,
) -> None:
    context = authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h").row_context
    spec_definition = _spec(context)
    spec_path = tmp_path / "spec.json"
    spec.write_document(spec_definition, spec_path)
    restored_spec = spec.load_spec(spec_path)
    original_mapping = (
        spec_definition.entities["entity"].datasets["observations"].mappings["result"]
    )
    restored_mapping = restored_spec.entities["entity"].datasets["observations"].mappings["result"]
    assert restored_mapping.row_context == original_mapping.row_context == context
    assert (
        "row_context"
        not in spec_definition.entities["entity"]
        .datasets["observations"]
        .mappings["result"]
        .binding.model_dump()
    )
    exported = json.loads(spec_path.read_text())
    exported_dataset = exported["entities"]["entity"]["datasets"]["observations"]
    exported_feature = exported_dataset["features"]["result"]
    assert "row_context" not in exported_feature
    assert exported_dataset["mappings"]["result"]["row_context"] == context.to_dict()
    assert "binding" not in exported_feature
    assert (
        "row_context"
        not in exported["entities"]["entity"]["datasets"]["observations"]["mappings"]["result"][
            "binding"
        ]
    )
    assert spec_definition.functions["calculate"].args["column"].type == "string"

    plan = compiler.Compiler(restored_spec).compile()
    operation = next(item for item in plan.callables if item.operation == "vectorize")
    assert operation.row_context == context
    assert all(item.row_context is None for item in plan.callables if item.operation != "vectorize")
    assert operation.arguments == {
        "dataset": "observations",
        "column": "temperature",
        "output": "result",
        "configuration": {"windows": ["8h", "24h"]},
    }
    assert plan.plan.resources["datasets"]["observations"]["order"] == [
        {"dimension": "$dimensions.timestamp", "direction": "asc"}
    ]
    plan_path = plan.export_json(tmp_path / "plan.json")
    restored_plan = uptimely_plan.ExecutionPlan.from_json(plan_path)
    assert restored_plan.plan == plan.plan
    result = engine_for_plan(restored_plan).run()
    assert not result.failures
    frame = next(iter(result.datasets.values()))
    assert frame["result"].to_list() == [11, 21]
    assert frame["timestamp"].to_list() == [
        datetime.datetime(2026, 1, 2),
        datetime.datetime(2026, 1, 1),
    ]

    render_explorer(spec_definition, tmp_path / "index.html")
    features_html = (tmp_path / "spec/features.html").read_text(encoding="utf-8")
    assert "result" in features_html
    assert "Row context:" not in features_html
    html = (tmp_path / "plan/stages.html").read_text(encoding="utf-8")
    assert "Row context" in html


def test_plan_context_is_present_in_portable_operations() -> None:
    plan = compiler.Compiler(_spec(context=authoring.current())).compile()
    operation = next(item for item in plan.callables if item.output == "result")
    assert operation.row_context == authoring.current()


def test_collapse_functions_execute_without_row_context() -> None:
    source = dataset.Dataset(
        id="observations",
        mappings=[
            mapping.Mapping(
                bind=bind.bind(ref.function(read_observations, operation="read")),
                outputs=[
                    feature.Feature(id="timestamp", type="datetime"),
                    feature.Feature(id="temperature", type="integer"),
                ],
            )
        ],
    )
    summary = dataset.Dataset(
        id="summary",
        mappings=[
            mapping.Mapping(
                id="summary",
                bind=bind.bind(
                    ref.function(maximum, operation="collapse"),
                    dataset=ref.dataset("observations").dataframe,
                    column=ref.feature("temperature").id,
                    output=ref.feature("temperature_max").id,
                ),
                inputs=[ref.feature("temperature")],
                outputs=[feature.Feature(id="temperature_max", type="integer")],
            )
        ],
    )
    timestamp = dimension.Dimension(id="timestamp", type="datetime")
    spec_definition = spec.from_python(
        entities=[
            entity.Entity(
                id="observation", name="Observation", dimensions=[timestamp], datasets=[source]
            ),
            entity.Entity(id="summary", name="Summary", dimensions=[], datasets=[summary]),
        ],
        dimensions=[timestamp],
    )
    plan = compiler.Compiler(spec_definition).compile()
    operation = next(item for item in plan.callables if item.operation == "collapse")
    assert operation.row_context is None
    assert operation.entrypoint.endswith(":maximum")
    assert operation.arguments == {
        "dataset": "observations",
        "column": "temperature",
        "output": "temperature_max",
    }
    output_dataset = spec_definition.entities["summary"].datasets["summary"]
    output = output_dataset.mappings["summary"]
    assert output.row_context is None
    payload = output.model_dump()
    assert "group_by" not in payload
    assert "row_context" not in payload["binding"]
    restored = uptimely_plan.Plan.from_dict(json.loads(json.dumps(plan.plan.to_dict())))
    assert restored == plan.plan
    result = engine_for_plan(uptimely_plan.ExecutionPlan(restored)).run()
    assert not result.failures
    assert result.datasets["summary"]["temperature_max"].to_list() == [20]
