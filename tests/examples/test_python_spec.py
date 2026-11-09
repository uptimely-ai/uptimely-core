import polars as pl
import pytest
from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension as pump_dimensions
from examples.pump_analytics.spec import spec as pump_telemetry_spec
from examples.pump_analytics.spec.profiles import (
    constants,
    pump,
    pump_category,
    pump_series,
    pump_telemetry,
    pump_telemetry_by_day,
    pump_telemetry_by_hour,
    pump_telemetry_by_minute,
)
from support import examples as example_support

from uptimely import spec
from uptimely.spec import python as python_spec
from uptimely.spec.python import binding_conversion

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def _read_transform_data() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "input_1": [1, 3], "input_2": [2, 4]})


def expand_data(source: pl.DataFrame) -> pl.DataFrame:
    return source.select("id", pl.col("input_1").alias("expanded"))


def test_aggregate_executes_independently() -> None:
    frame = pl.LazyFrame({"pump": ["a", "a"], "temperature": [10.0, 20.0]})

    result = analytics.aggregate(frame, "temperature", "max", ["pump"], "maximum")

    assert isinstance(result, pl.LazyFrame)
    assert result.collect().to_dicts() == [{"pump": "a", "maximum": 20.0}]
    assert frame.collect().to_dicts() == [
        {"pump": "a", "temperature": 10.0},
        {"pump": "a", "temperature": 20.0},
    ]


def test_pump_dimensions_are_declared_in_spec_order() -> None:
    inferred = pump_telemetry_spec.python_spec.to_model().dimensions

    assert list(inferred) == ["machine_dimension", "machine_timestamp"]
    assert list(inferred["machine_dimension"].resolutions) == [
        "machine",
        "machine_series",
        "machine_category",
    ]
    assert inferred["machine_dimension"].resolutions["machine"].parent == "machine_series"
    assert inferred["machine_dimension"].resolutions["machine_series"].parent == "machine_category"
    assert list(inferred["machine_timestamp"].resolutions) == [
        "timestamp",
        "minute",
        "hour",
        "day",
    ]
    assert inferred["machine_timestamp"].resolutions["timestamp"].parent == "minute"
    assert inferred["machine_timestamp"].resolutions["minute"].parent == "hour"
    assert inferred["machine_timestamp"].resolutions["hour"].parent == "day"
    assert pump_dimensions.FACILITY_DIMENSION.id == "facility_dimension"
    assert [resolution.id for resolution in pump_dimensions.FACILITY_DIMENSION.resolutions] == [
        "production_line",
        "plant",
    ]
    assert pump_dimensions.FACILITY_DIMENSION.resolutions[0].parent == "plant"


def test_pump_profiles_are_declared_in_spec_order() -> None:
    expected = [
        pump_telemetry.PumpTelemetry,
        pump.Pump,
        constants.Constants,
        pump_series.PumpSeries,
        pump_category.PumpCategory,
        pump_telemetry_by_minute.PumpTelemetryByMinute,
        pump_telemetry_by_hour.PumpTelemetryByHour,
        pump_telemetry_by_day.PumpTelemetryByDay,
    ]

    assert [
        profile.category for profile in pump_telemetry_spec.python_spec.to_model().profiles.values()
    ] == [
        "Telemetry",
        "Machines",
        "Configuration",
        "Machines",
        "Machines",
        "Telemetry",
        "Telemetry",
        "Telemetry",
    ]
    assert [type(profile) for profile in pump_telemetry_spec.python_spec.profiles] == expected
    assert [profile.id for profile in pump_telemetry_spec.python_spec.profiles] == [
        "pump_telemetry",
        "pump",
        "constants",
        "pump_series",
        "pump_category",
        "pump_telemetry_by_minute",
        "pump_telemetry_by_hour",
        "pump_telemetry_by_day",
    ]
    assert pump_telemetry.PumpTelemetry.grain == [
        pump_dimensions.MACHINE_DIMENSION.resolution("machine"),
        pump_dimensions.MACHINE_TIMESTAMP.resolution("timestamp"),
    ]
    assert pump.Pump.grain == [
        pump_dimensions.MACHINE_DIMENSION.resolution("machine"),
    ]


def test_argument_definition_supports_recursive_compact_types() -> None:
    assert binding_conversion.argument_definition({"value": 1.0}) == {"type": "object{str: float}"}
    assert binding_conversion.argument_definition({"value": {"nested": 1.0}}) == {
        "type": "object{str: object{str: float}}"
    }
    assert binding_conversion.argument_definition(
        {"dimensions": [python_spec.ref.dimension("plant")]}
    ) == {"type": "object{str: array[string]}"}
    assert binding_conversion.argument_definition({"value": 1.0, "other": "text"}) == {
        "type": "object"
    }


def test_function_catalog_functions_declare_kinds() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    function_kinds = {function.kind for function in spec_definition.functions.root.values()}
    assert "vectorize" in function_kinds


def test_recommended_flow_rate_binds_polars_with_columns() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    operator = spec_definition.profiles["pump_telemetry"].assembly["recommended_flow_rate"]
    template = spec_definition.functions.root[operator.compute.function]

    assert template.entrypoint == "polars.lazyframe.frame:LazyFrame.with_columns"
    assert template.kind == "vectorize"
    assert template.validate_signature is False
    assert operator.compute.inferred_feature_inputs == ("flow_rate",)
    assert operator.output_features == ["recommended_flow_rate"]


def test_example_manifest_parses_complete_spec() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_from_directory = spec.load_spec(SPEC_PATH.parent)

    assert spec_from_directory == spec_definition
    assert "facility_dimension" not in spec_definition.dimensions
    assert set(spec_definition.profiles) == {
        "pump_telemetry",
        "pump",
        "constants",
        "pump_series",
        "pump_category",
        "pump_telemetry_by_minute",
        "pump_telemetry_by_hour",
        "pump_telemetry_by_day",
    }
    assert spec_definition.profiles["pump_telemetry"].dimension_ids == [
        "machine_dimension",
        "machine_timestamp",
    ]
    assert spec_definition.profiles["pump_telemetry"].grain_reference_set == {
        ("machine_dimension", "machine"),
        ("machine_timestamp", "timestamp"),
    }
    assert spec_definition.grain_keys_by_profile["pump_telemetry"] == [
        "pump_id",
        "timestamp",
    ]
    assert isinstance(spec_definition, spec.Spec)
    assert spec_definition.source.name == "python_api"
    assert spec_definition.source.generated is True
    assert {function.kind for function in spec_definition.functions.root.values()} == {
        "read",
        "write",
        "vectorize",
        "collapse",
        "expand",
        "escape",
        "merge",
    }
    assert "aggregate" not in spec_definition.functions.by_kind("vectorize")
    assert len(spec_definition.functions.by_kind("vectorize")) == 9

    pump_profile = spec_definition.profiles["pump"]
    collapse = pump_profile.assembly["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.compute.function == "aggregate"
    assert "bearing_temperature_max" in collapse.output_features


def test_spec_from_profiles_python_api() -> None:
    spec_definition = spec.from_python(
        profiles=pump_telemetry_spec.python_spec.profiles,
        name=pump_telemetry_spec.python_spec.name,
    )

    assert set(spec_definition.profiles) == {
        "pump_telemetry",
        "pump",
        "constants",
        "pump_series",
        "pump_category",
        "pump_telemetry_by_minute",
        "pump_telemetry_by_hour",
        "pump_telemetry_by_day",
    }
    assert spec_definition.name == pump_telemetry_spec.python_spec.name
    assert spec_definition.source.name == "python_api"
    assert spec_definition.source.generated is True
    assert spec_definition.functions.by_kind("read")


def test_example_timestamp_order_matches_python_declaration() -> None:
    authored = spec.from_python(
        profiles=pump_telemetry_spec.python_spec.profiles,
    )
    exported = spec.load_spec(SPEC_PATH)
    expected = [
        {
            "dimension": "machine_timestamp",
            "resolution": "timestamp",
            "direction": "asc",
        }
    ]
    for spec_definition in (authored, exported):
        assert [
            key.model_dump() for key in spec_definition.profiles["pump_telemetry"].order
        ] == expected
        assert spec_definition.profiles["pump"].order == []


def test_sources_and_transforms_python_spec() -> None:
    id_dimension = python_spec.dimension.Dimension(
        id="id",
        resolutions=[python_spec.dimension.Resolution(id="id", key="id", type="integer")],
    )
    region_dimension = python_spec.dimension.Dimension(
        id="region",
        resolutions=[python_spec.dimension.Resolution(id="region", key="region", type="string")],
    )
    source = python_spec.profile.Profile(
        id="transformed_dataset",
        grain=[id_dimension.resolution("id")],
        assembly=[
            python_spec.Operator(
                id="read",
                interface=python_spec.Interface(
                    inputs=[],
                    outputs=[python_spec.feature.Feature(id="input_1")],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(_read_transform_data, kind="read"),
                    arguments={},
                ),
            )
        ],
    )
    target = python_spec.profile.Profile(
        id="target",
        grain=[
            id_dimension.resolution("id"),
            region_dimension.resolution("region"),
        ],
        assembly=[
            python_spec.Operator(
                id="read",
                interface=python_spec.Interface(
                    inputs=[],
                    outputs=[python_spec.feature.Feature(id="target_value")],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(_read_transform_data, kind="read"),
                    arguments={},
                ),
            ),
            python_spec.Operator(
                id="expand_data",
                interface=python_spec.Interface(
                    inputs=[python_spec.ref.feature("input_1")],
                    outputs=[python_spec.feature.Feature(id="input_2")],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(expand_data, kind="expand"),
                    arguments={
                        "source": python_spec.ref.profile("transformed_dataset").dataset,
                    },
                ),
            ),
        ],
    )
    summary = python_spec.profile.Profile(
        id="summary",
        grain=[id_dimension.resolution("id")],
        assembly=[
            python_spec.Operator(
                id="collapse_data",
                interface=python_spec.Interface(
                    inputs=[python_spec.ref.feature("input_2")],
                    outputs=[python_spec.feature.Feature(id="collapsed_feature")],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(analytics.aggregate, kind="collapse"),
                    arguments={
                        "dataset": python_spec.ref.profile("target").dataset,
                        "feature": python_spec.ref.feature("input_2").id,
                        "group_by": python_spec.ref.profile().grain.ids,
                        "output": python_spec.ref.feature("collapsed_feature").id,
                    },
                ),
            )
        ],
    )
    spec_definition = spec.from_python(
        profiles=[source, target, summary],
        name="transforms_test",
    )

    ds_model = spec_definition.profiles["target"]
    assert set(ds_model.assembly) == {"read", "expand_data"}
    assert {"target_value", "input_2"} <= set(ds_model.all_features)
    expand = ds_model.assembly["expand_data"]
    assert expand.compute.function == "expand_data"
    assert expand.compute.model_dump()["args"] == {
        "source": "$profiles.transformed_dataset.dataset",
    }
    assert expand.input_features == ["input_1"]
    collapse = spec_definition.profiles["summary"].assembly["collapse_data"]
    assert collapse.compute.function == "aggregate"
    assert collapse.compute.model_dump()["args"] == {
        "dataset": "$profiles.target.dataset",
        "feature": "$features.input_2.id",
        "group_by": "$profiles.@.grain.ids",
        "output": "$features.collapsed_feature.id",
    }
    assert collapse.output_features == ["id", "collapsed_feature"]
    assert spec_definition.functions["aggregate"].kind == "collapse"
