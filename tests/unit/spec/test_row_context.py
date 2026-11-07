import dataclasses
import datetime
import json
import pathlib
import types

import polars as pl
import pydantic
import pytest
from support import execution as execution_support

from uptimely import compiler, row_context, spec
from uptimely import plan as uptimely_plan
from uptimely.explorer import presentation
from uptimely.spec import function_kinds as functions
from uptimely.spec.python import (
    assembly,
    binding_conversion,
    dimension,
    feature,
    profile,
    ref,
)
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


def maximum(dataset: pl.DataFrame, column: str, output: str) -> pl.DataFrame:
    """Return a whole-dataset maximum without observation-context requirements."""
    return dataset.select(pl.col(column).max().alias(output))


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
                grain=[profile.Grain(timestamp, "timestamp")],
                order=[profile.Order(timestamp, "timestamp", "asc")] if ordered else [],
                assembly=[
                    assembly.Operator(
                        id="read_observations",
                        interface=assembly.Interface(
                            inputs=[],
                            outputs=[
                                feature.Feature(id="timestamp", type=dimension_type),
                                feature.Feature(id="temperature", type="integer"),
                            ],
                        ),
                        compute=assembly.Binding(
                            function=ref.function(read_observations, kind="read"),
                            arguments={},
                        ),
                    ),
                    assembly.Operator(
                        id="result",
                        interface=assembly.Interface(
                            inputs=[ref.feature("temperature")],
                            outputs=[feature.Feature(id="result", type="integer")],
                        ),
                        compute=assembly.Binding(
                            function=ref.function(calculate, kind="vectorize"),
                            arguments={
                                "dataset": ref.profile().data,
                                "column": ref.feature("temperature").id,
                                "output": ref.feature("result").id,
                                "configuration": {"windows": ["8h", "24h"]},
                            },
                        ),
                        row_context=context,
                    ),
                ],
            )
        ]
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
    declaration = assembly.Operator(
        id="declaration",
        interface=assembly.Interface(
            inputs=[],
            outputs=[],
        ),
        compute=assembly.Binding(
            function=ref.function(f"{__name__}:calculate", kind="vectorize"),
            arguments={
                "configuration": {
                    "windows": [
                        authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h"),
                        authoring.time(
                            "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
                        ),
                    ]
                }
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
            interface=assembly.Interface(
                inputs=[],
                outputs=[],
            ),
            compute=assembly.Binding(
                function=ref.function(calculate, kind="vectorize"),
                arguments={"configuration": [first, second]},
            ),
        )
    with pytest.raises(ValueError, match="one measurement"):
        assembly.Operator(
            id="operator",
            interface=assembly.Interface(
                inputs=[],
                outputs=[],
            ),
            compute=assembly.Binding(
                function=ref.function(calculate, kind="vectorize"),
                arguments={"configuration": [first, authoring.rows(8, before=7)]},
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


def test_unknown_current_and_whole_dataset_context_are_distinct():
    assert (
        assembly.Operator(
            id="operator",
            interface=assembly.Interface(
                inputs=[],
                outputs=[],
            ),
            compute=assembly.Binding(
                function=ref.function(calculate, kind="vectorize"),
                arguments={},
            ),
        ).row_context
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
    _spec(authoring.dataset(), ordered=False)


@pytest.mark.parametrize("kind", [kind for kind in functions.FUNCTION_KINDS if kind != "merge"])
@pytest.mark.parametrize("dimension_change", ["preserve", "remove"])
def test_row_context_dataset_selection_follows_dimension_contract(
    kind: functions.FunctionKindId,
    dimension_change: functions.DimensionChange,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    configuration["functions"]["calculate"]["kind"] = kind
    document = spec.Spec.model_validate(configuration)
    definitions = dict(functions.FUNCTION_KINDS)
    definitions[kind] = dataclasses.replace(definitions[kind], dimension_change=dimension_change)
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    key = ("summary", "result")
    expected_source = "observations" if dimension_change == "remove" else "summary"
    assert document.get_row_context_profile(key) is document.profiles[expected_source]
    assert (
        document.get_row_context_dimensions(key) == document.dimensions_by_profile[expected_source]
    )
    if dimension_change == "remove":
        row_context_rules.validate_dataset_order(document)
        row_context_rules.validate_dimension(document)
        row_context_rules.validate_dimension_order(document)
    else:
        with pytest.raises(ValueError, match="requires profile order"):
            row_context_rules.validate_dataset_order(document)
        with pytest.raises(ValueError, match="not in the input profile"):
            row_context_rules.validate_dimension(document)
        with pytest.raises(ValueError, match="must occur in profile order"):
            row_context_rules.validate_dimension_order(document)
    row_context_rules.validate_dimension_type(document)


def test_row_context_accessors_preserve_unresolved_sources() -> None:
    configuration = _spec(authoring.current()).model_dump()
    configuration["functions"]["calculate"]["kind"] = "collapse"
    configuration["profiles"]["observations"]["assembly"]["result"]["interface"]["inputs"] = [
        "$features.missing"
    ]
    document = spec.Spec.model_validate(configuration)
    key = ("observations", "result")

    assert document.get_row_context_profile(key) is None
    assert document.get_row_context_dimensions(key) is None


def test_spec_plan_execution_and_presentation_preserve_context(
    tmp_path: pathlib.Path, engine_for_plan: execution_support.EngineFactory
) -> None:
    context = authoring.time(
        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
    ).row_context
    spec_definition = _spec(context)
    path = tmp_path / "spec.json"
    spec.write_document(spec_definition, path)
    payload = json.loads(path.read_text())
    authored_dataset = payload["profiles"]["observations"]
    assert "row_context" not in authored_dataset["features"]["result"]
    assert authored_dataset["assembly"]["result"]["row_context"] == context.to_dict()
    restored = spec.load_spec(path)
    compiled = compiler.Compiler().compile(restored)
    operation = next(item for item in compiled.invocations if item.function_kind == "vectorize")
    assert operation.input_features == ["temperature"]
    assert operation.row_context == context
    portable = uptimely_plan.from_dict(uptimely_plan.to_dict(compiled))
    result = engine_for_plan(portable, spec_definition=restored).run()
    assert not result.failures
    frame = result.main_frames["observations"]
    assert frame.sort("timestamp")["result"].to_list() == [21, 11]
    data = presentation.build_presentation_data(restored, compiled)
    rendered_operation = next(
        step
        for stage in data["stages"]
        for step in stage["steps"]
        if step["function"] == "calculate"
    )
    assert rendered_operation["row_context"] == context.to_dict()


@pytest.mark.parametrize("operation", ["read", "expand", "collapse", "vectorize"])
def test_all_data_mappings_preserve_annotated_context(operation):
    declaration = assembly.Operator(
        id="declaration",
        interface=assembly.Interface(
            inputs=[],
            outputs=[],
        ),
        compute=assembly.Binding(
            function=ref.function(f"{__name__}:calculate", kind=operation),
            arguments={"configuration": {"windows": [authoring.rows(8, before=7)]}},
        ),
    )
    assert declaration.to_model().row_context.before.rows == 7
    assert declaration.to_model().compute.model_dump()["args"] == {
        "configuration": {"windows": [8]}
    }


def test_spec_plan_and_batch_execution_preserve_context_and_arguments(
    tmp_path: pathlib.Path,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    context = authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h").row_context
    spec_definition = _spec(context)
    spec_path = tmp_path / "spec.json"
    spec.write_document(spec_definition, spec_path)
    restored_spec = spec.load_spec(spec_path)
    original_mapping = spec_definition.profiles["observations"].assembly["result"]
    restored_mapping = restored_spec.profiles["observations"].assembly["result"]
    assert restored_mapping.row_context == original_mapping.row_context == context
    assert (
        "row_context"
        not in spec_definition.profiles["observations"].assembly["result"].compute.model_dump()
    )
    exported = json.loads(spec_path.read_text())
    exported_dataset = exported["profiles"]["observations"]
    exported_feature = exported_dataset["features"]["result"]
    assert "row_context" not in exported_feature
    assert exported_dataset["assembly"]["result"]["row_context"] == context.to_dict()
    assert "compute" not in exported_feature
    assert (
        "row_context" not in exported["profiles"]["observations"]["assembly"]["result"]["compute"]
    )
    assert spec_definition.functions["calculate"].args["column"].type == "string"

    plan = compiler.Compiler().compile(restored_spec)
    operation = next(item for item in plan.invocations if item.function_kind == "vectorize")
    assert operation.row_context == context
    assert all(
        item.row_context is None for item in plan.invocations if item.function_kind != "vectorize"
    )
    assert operation.arguments == {
        "dataset": "observations",
        "column": "temperature",
        "output": "result",
        "configuration": {"windows": ["8h", "24h"]},
    }
    assert spec_definition.profiles["observations"].order == [
        spec.Order(dimension="timestamp", resolution="timestamp", direction="asc")
    ]
    plan_path = uptimely_plan.export_json(plan, tmp_path / "plan.json")
    restored_plan = uptimely_plan.from_json(plan_path)
    assert restored_plan == plan
    result = engine_for_plan(restored_plan, spec_definition=restored_spec).run()
    assert not result.failures
    frame = next(iter(result.main_frames.values()))
    assert frame["result"].to_list() == [11, 21]
    assert frame["timestamp"].to_list() == [
        datetime.datetime(2026, 1, 2),
        datetime.datetime(2026, 1, 1),
    ]

    data = presentation.build_presentation_data(restored_spec, restored_plan)
    step = next(
        step
        for stage in data["stages"]
        for step in stage["steps"]
        if step["function"] == "calculate"
    )
    assert step["row_context"] == context.to_dict()


def test_plan_context_is_present_in_portable_operations() -> None:
    plan = compiler.Compiler().compile(_spec(context=authoring.current()))
    operation = next(item for item in plan.invocations if "result" in item.output_features)
    assert operation.row_context == authoring.current()


def test_collapse_functions_execute_without_row_context(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    source = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="read_observations",
                interface=assembly.Interface(
                    inputs=[],
                    outputs=[
                        feature.Feature(id="timestamp", type="datetime"),
                        feature.Feature(id="temperature", type="integer"),
                    ],
                ),
                compute=assembly.Binding(
                    function=ref.function(read_observations, kind="read"),
                    arguments={},
                ),
            )
        ],
    )
    summary = profile.Profile(
        id="summary",
        assembly=[
            assembly.Operator(
                id="summary",
                interface=assembly.Interface(
                    inputs=[ref.feature("temperature")],
                    outputs=[feature.Feature(id="temperature_max", type="integer")],
                ),
                compute=assembly.Binding(
                    function=ref.function(maximum, kind="collapse"),
                    arguments={
                        "dataset": ref.profile("observations").data,
                        "column": ref.feature("temperature").id,
                        "output": ref.feature("temperature_max").id,
                    },
                ),
            )
        ],
    )
    timestamp = dimension.Dimension(
        id="timestamp",
        resolutions=[dimension.Resolution(id="timestamp", key="timestamp", type="datetime")],
    )
    spec_definition = spec.from_python(
        profiles=[
            profile.Profile(
                id=source.id,
                grain=[profile.Grain(timestamp, "timestamp")],
                assembly=source.assembly,
            ),
            profile.Profile(
                id=summary.id,
                assembly=summary.assembly,
            ),
        ]
    )
    plan = compiler.Compiler().compile(spec_definition)
    operation = next(item for item in plan.invocations if item.function_kind == "collapse")
    assert operation.row_context is None
    assert operation.entrypoint.endswith(":maximum")
    assert operation.arguments == {
        "dataset": "observations",
        "column": "temperature",
        "output": "temperature_max",
    }
    output_dataset = spec_definition.profiles["summary"]
    output = output_dataset.assembly["summary"]
    assert output.row_context is None
    payload = output.model_dump()
    assert "group_by" not in payload
    assert "row_context" not in payload["compute"]
    restored = uptimely_plan.from_dict(json.loads(json.dumps(uptimely_plan.to_dict(plan))))
    assert restored == plan
    result = engine_for_plan(restored, spec_definition=spec_definition).run()
    assert not result.failures
    assert result.main_frames["summary"]["temperature_max"].to_list() == [20]
