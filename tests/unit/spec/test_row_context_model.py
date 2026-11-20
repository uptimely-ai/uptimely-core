import datetime
import typing

import polars as pl
import pydantic
import pytest

from uptimely import compiler, row_context, spec
from uptimely.spec import arg_types
from uptimely.spec.python import assembly, binding_conversion, dimension, feature, profile, ref
from uptimely.spec.python import row_context as authoring
from uptimely.spec.validation.rules import row_context as row_context_rules


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


def _spec(context=None, *, ordered=True, dimension_type="datetime"):
    timestamp = dimension.Dimension(
        id="timestamp",
        resolutions=[
            dimension.Resolution(
                id="timestamp",
                key="timestamp",
                type=dimension_type,
            )
        ],
    )
    return spec.from_python(
        profiles=[
            profile.Profile(
                id="observations",
                grain=[timestamp.resolution("timestamp")],
                order=[profile.Order(timestamp, "timestamp", "asc")] if ordered else [],
                assembly=[
                    assembly.Operator(
                        id="read_observations",
                        inputs=[],
                        outputs=[
                            feature.Feature(id="temperature", type="integer"),
                        ],
                        compute=assembly.Bind(
                            ref.function(read_observations),
                        ),
                    ),
                    assembly.Operator(
                        id="result",
                        inputs=[ref.feature("temperature")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        compute=assembly.Bind(
                            ref.function(calculate),
                            dataset=ref.profile().dataset,
                            column=ref.feature("temperature").id,
                            output=ref.feature("result").id,
                            configuration={"windows": ["8h", "24h"]},
                        ),
                        row_context=context,
                    ),
                ],
            )
        ]
    )


@pytest.mark.parametrize(
    ("attribute", "context", "expected_value", "expected_type"),
    [
        ("before", row_context.RowContext(before=1), 1, arg_types.INTEGER),
        (
            "before",
            row_context.RowContext(dimension="$dimensions.timestamp", before={"time": "8h"}),
            "8h",
            arg_types.STRING,
        ),
        (
            "before",
            row_context.RowContext(before=row_context.UNBOUNDED),
            row_context.UNBOUNDED,
            arg_types.STRING,
        ),
        ("before", row_context.RowContext(), 0, arg_types.INTEGER),
        (
            "dimension",
            row_context.RowContext(dimension="$dimensions.timestamp"),
            "timestamp",
            arg_types.STRING,
        ),
    ],
)
def test_row_context_references_resolve_scalar_extents(
    attribute: typing.Literal["before", "dimension"],
    context: row_context.RowContext,
    expected_value: int | str,
    expected_type: str,
) -> None:
    declaration = assembly.Operator(
        id="result",
        row_context=context,
        compute=assembly.Bind(
            ref.function("external:calculate", returns="dataframe"),
            **{attribute: ref.row_context(attribute)},
        ),
    )
    model = declaration.to_model()

    assert declaration.function_catalog()["calculate"].args[attribute].type == expected_type
    assert model.resolve_args(
        function_id=model.compute.function,
        profile_id="observations",
        identifiers_by_profile={},
        resources={},
    ) == {attribute: expected_value}
    assert list(model.model_dump()) == [
        "interface",
        "row_context",
        "compute",
        "is_workflow",
        "merge",
    ]


@pytest.mark.parametrize("extent", [-1, True, 1.5])
def test_row_context_integer_shorthand_remains_strict(extent: object) -> None:
    with pytest.raises(pydantic.ValidationError):
        row_context.RowContext(before=extent)


def test_row_context_reference_is_validated_and_resolved_during_compilation() -> None:
    configuration = _spec(row_context.RowContext(before=2)).model_dump()
    arguments = configuration["profiles"]["observations"]["assembly"]["result"]["compute"]["args"]
    arguments["configuration"]["windows"] = [ref.row_context("before").to_model()]

    declaration = spec.Spec.model_validate(configuration)
    plan = compiler.Compiler().compile(declaration)
    invocation = next(item for item in plan.invocations if item.row_context is not None)

    assert invocation.arguments["configuration"] == {"windows": [2]}


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


def test_operator_consolidates_directional_maxima_and_unwraps_arguments():
    declaration = assembly.Operator(
        id="declaration",
        inputs=[],
        outputs=[],
        compute=assembly.Bind(
            ref.function(f"{__name__}:calculate", returns="dataframe"),
            configuration={
                "windows": [
                    authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h"),
                    authoring.time(
                        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
                    ),
                ]
            },
        ),
        row_context=authoring.time("explicit", dimension=ref.dimension("timestamp"), after="3h"),
    )
    assert declaration.to_model().row_context.to_dict() == {
        "dimension": "$dimensions.timestamp",
        "before": {"time": "24h"},
        "after": {"time": "3h"},
    }
    assert declaration.to_model().compute.model_dump()["args"] == {
        "configuration": {"windows": ["8h", "24h"]}
    }
    assert binding_conversion.argument_definition(
        declaration.bound_arguments()["configuration"]
    ) == {"type": "object{str: array[string]}"}


def test_consolidation_rejects_different_dimensions_and_measurements():
    first = authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h")
    second = authoring.time("8h", dimension=ref.dimension("other"), before="8h")
    with pytest.raises(ValueError, match="one dimension"):
        assembly.Operator(
            id="operator",
            inputs=[],
            outputs=[],
            compute=assembly.Bind(
                ref.function(calculate),
                configuration=[first, second],
            ),
        )
    with pytest.raises(ValueError, match="one measurement"):
        assembly.Operator(
            id="operator",
            inputs=[],
            outputs=[],
            compute=assembly.Bind(
                ref.function(calculate),
                configuration=[first, authoring.rows(8, before=7)],
            ),
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


def test_unknown_current_and_all_rows_context_are_distinct():
    assert (
        assembly.Operator(
            id="operator",
            inputs=[],
            outputs=[],
            compute=assembly.Bind(
                ref.function(calculate),
            ),
        ).row_context
        is None
    )
    assert authoring.current().to_dict() == {"before": {}, "after": {}}
    whole = authoring.all_rows()
    assert whole.to_dict() == {"before": "unbounded", "after": "unbounded"}
    assert not whole.requires_order
    assert whole.merge(authoring.rows(8, before=7)) == whole
    assert row_context.RowContext.model_validate(whole.to_dict()) == whole
    assert row_context.RowContext(before="unbounded").requires_order


def test_unbounded_dominates_bounded_directional_requirements():
    left = authoring.time(
        "native", dimension=ref.dimension("timestamp"), before=row_context.UNBOUNDED
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
            "not in the input profile",
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
    with pytest.raises(ValueError, match="requires profile order"):
        _spec(authoring.rows(1, before=1).row_context, ordered=False)
    _spec(authoring.current(), ordered=False)
    _spec(authoring.all_rows(), ordered=False)


def test_row_context_dataset_selection_follows_collapse_relationship() -> None:
    configuration = _spec().model_dump()
    source = configuration["profiles"]["observations"]
    operator = source["assembly"].pop("result")
    output = source["features"].pop("result")
    operator["row_context"] = authoring.time(
        "1h", dimension=ref.dimension("timestamp"), before="1h"
    ).row_context.to_dict()
    configuration["profiles"]["summary"] = {
        "name": "Summary",
        "grain": [],
        "features": {"result": output},
        "assembly": {"result": operator},
    }
    document = spec.Spec.model_validate(configuration)

    key = ("summary", "result")
    assert (
        document.operators_by_key[key].grain_relationships(document, key)["observations"]
        == "collapse"
    )
    assert document.get_row_context_profile(key) is document.profiles["observations"]
    assert (
        document.get_row_context_dimensions(key) == document.dimensions_by_profile["observations"]
    )
    row_context_rules.validate_row_context_profile_order(document)
    row_context_rules.validate_dimension(document)
    row_context_rules.validate_dimension_order(document)
    row_context_rules.validate_dimension_type(document)


def test_row_context_accessors_preserve_unresolved_sources() -> None:
    configuration = _spec(authoring.current()).model_dump()
    configuration["profiles"]["observations"]["assembly"]["result"]["interface"]["inputs"] = [
        "$features.missing"
    ]
    document = spec.Spec.model_validate(configuration)
    key = ("observations", "result")
    assert document.get_row_context_profile(key) is None
    assert document.get_row_context_dimensions(key) is None
