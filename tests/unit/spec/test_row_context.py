import datetime
import json
import pathlib

import polars as pl
import pydantic
import pytest

from uptimely import compile, engine, plan, row_context, spec
from uptimely.spec.json_spec import json_model
from uptimely.spec.python_spec import bind, dataset, dimension, feature, mapping, ref
from uptimely.spec.python_spec import row_context as authoring


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


def _specification(context=None, *, ordered=True, dimension_type="datetime"):
    return spec.Specification.from_python(
        datasets=[
            dataset.Dataset(
                id="observations",
                order=[dataset.Order(ref.dimension("timestamp"), "asc")] if ordered else [],
                mappings=[
                    mapping.Read(
                        bind=bind.bind(read_observations),
                        outputs=[
                            feature.Feature(id="timestamp", type=dimension_type),
                            feature.Feature(id="temperature", type="integer"),
                        ],
                    ),
                    mapping.Vectorize(
                        id="result",
                        inputs=[ref.feature("temperature")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        row_context=context,
                        bind=bind.bind(
                            calculate,
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
    declaration = mapping.Vectorize(
        bind=bind.bind(
            calculate,
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
        mapping.Vectorize(bind=bind.bind(calculate, configuration=[first, second]))
    with pytest.raises(ValueError, match="one measurement"):
        mapping.Vectorize(
            bind=bind.bind(
                calculate,
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
    assert mapping.Vectorize(bind=bind.bind(calculate)).row_context is None
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
        _specification(context, dimension_type=dimension_type)


def test_directional_context_requires_dataset_order():
    with pytest.raises(ValueError, match="requires dataset order"):
        _specification(authoring.rows(1, before=1).row_context, ordered=False)
    _specification(authoring.current(), ordered=False)
    _specification(authoring.dataset(), ordered=False)


def test_specification_plan_execution_and_docs_preserve_context(tmp_path: pathlib.Path):
    context = authoring.time(
        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
    ).row_context
    specification = _specification(context)
    path = tmp_path / "spec.json"
    specification.to_json(path)
    payload = json.loads(path.read_text())
    authored_dataset = payload["entities"]["entity"]["datasets"][0]
    assert "row_context" not in authored_dataset["features"]["result"]
    assert authored_dataset["mappings"]["result"]["row_context"] == context.to_dict()
    restored = spec.Specification.from_json(path)
    compiled = compile.Compiler(restored).compile()
    operation = next(item for item in compiled.operations if item.kind == "vectorize")
    assert operation.input_features == ["temperature"]
    assert operation.row_context == context
    portable = plan.ExecutionPlan(plan.Plan.from_dict(compiled.to_dict()))
    result = engine.Engine(portable).execute()
    assert not result.failures
    frame = result.datasets["entity", "observations"]
    assert frame.sort("timestamp")["result"].to_list() == [21, 11]
    assert "Row context:" in restored.create_html(tmp_path / "spec.html").read_text()
    assert "Row context" in portable.export_html(tmp_path / "plan.html").read_text()


@pytest.mark.parametrize(
    "kind", [mapping.Read, mapping.Expand, mapping.Collapse, mapping.Vectorize]
)
def test_all_data_mappings_preserve_annotated_context(kind):
    declaration = kind(
        bind=bind.bind(calculate, configuration={"windows": [authoring.rows(8, before=7)]})
    )
    assert declaration.to_model().row_context.before.rows == 7
    assert declaration.to_model().binding.args == {"configuration": {"windows": [8]}}


def test_context_is_mapping_metadata_not_an_argument():
    with pytest.raises(pydantic.ValidationError):
        json_model.Binding(function="calculate", row_context={})
