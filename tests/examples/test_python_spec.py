import polars as pl
import pytest
from examples.pump_analytics.functions import analytics
from examples.pump_analytics.spec import dimension as pump_dimensions
from examples.pump_analytics.spec import spec as pump_telemetry_spec
from examples.pump_analytics.spec.profiles import constants, external_workflow, pump, telemetry
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

    assert list(inferred) == ["machine", "timestamp"]
    assert list(inferred["machine"].resolutions) == [
        "machine",
        "production_line",
        "plant",
    ]
    assert inferred["machine"].resolutions["machine"].parent == "production_line"
    assert inferred["machine"].resolutions["production_line"].parent == "plant"


def test_pump_profiles_are_declared_in_spec_order() -> None:
    expected = [
        telemetry.Telemetry,
        pump.Pump,
        external_workflow.PumpExternalWorkflow,
        constants.Constants,
    ]

    assert [
        profile.category for profile in pump_telemetry_spec.python_spec.to_model().profiles.values()
    ] == ["Telemetry", "Machines", "Machines", "Configuration"]
    assert [type(profile) for profile in pump_telemetry_spec.python_spec.profiles] == expected
    assert [profile.id for profile in pump_telemetry_spec.python_spec.profiles] == [
        "pump_telemetry",
        "pump_profile",
        "pump_external_workflow",
        "constants",
    ]
    assert telemetry.Telemetry.grain == [
        python_spec.Grain(pump_dimensions.MACHINE, "machine"),
        python_spec.Grain(pump_dimensions.TIMESTAMP, "timestamp"),
    ]
    assert pump.Pump.grain == [
        python_spec.Grain(pump_dimensions.MACHINE, "machine"),
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


def test_example_manifest_parses_complete_spec() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_from_directory = spec.load_spec(SPEC_PATH.parent)

    assert spec_from_directory == spec_definition
    assert spec_definition.dimensions["machine"].resolutions["machine"].parent == (
        "production_line"
    )
    assert set(spec_definition.profiles) == {
        "pump_telemetry",
        "pump_profile",
        "pump_external_workflow",
        "constants",
    }
    assert spec_definition.profiles["pump_telemetry"].dimension_ids == [
        "machine",
        "timestamp",
    ]
    assert spec_definition.profiles["pump_telemetry"].grain_reference_set == {
        ("machine", "machine"),
        ("timestamp", "timestamp"),
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
    }
    assert "aggregate" not in spec_definition.functions.by_kind("vectorize")
    assert len(spec_definition.functions.by_kind("vectorize")) == 7

    pump_profile = spec_definition.profiles["pump_profile"]
    collapse = pump_profile.actions["bearing_temperature_by_pump"]
    assert not hasattr(collapse, "source")
    assert collapse.binding.function == "aggregate"
    assert "bearing_temperature_max" in collapse.output_features


def test_spec_from_profiles_python_api() -> None:
    spec_definition = spec.from_python(
        profiles=pump_telemetry_spec.python_spec.profiles,
        name=pump_telemetry_spec.python_spec.name,
    )

    assert set(spec_definition.profiles) == {
        "pump_telemetry",
        "pump_profile",
        "pump_external_workflow",
        "constants",
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
    expected = [{"dimension": "timestamp", "resolution": "timestamp", "direction": "asc"}]
    for spec_definition in (authored, exported):
        assert [
            key.model_dump() for key in spec_definition.profiles["pump_telemetry"].order
        ] == expected
        assert spec_definition.profiles["pump_profile"].order == []


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
        grain=[python_spec.Grain(id_dimension, "id")],
        assembly=[
            python_spec.actions.Operator(
                id="read",
                inputs=[],
                function=python_spec.ref.function(_read_transform_data, kind="read"),
                arguments={},
                outputs=[python_spec.feature.Feature(id="input_1")],
            )
        ],
    )
    target = python_spec.profile.Profile(
        id="target",
        grain=[
            python_spec.Grain(id_dimension, "id"),
            python_spec.Grain(region_dimension, "region"),
        ],
        assembly=[
            python_spec.actions.Operator(
                id="read",
                inputs=[],
                function=python_spec.ref.function(_read_transform_data, kind="read"),
                arguments={},
                outputs=[python_spec.feature.Feature(id="target_value")],
            ),
            python_spec.actions.Operator(
                id="expand_data",
                inputs=[python_spec.ref.feature("input_1")],
                function=python_spec.ref.function(expand_data, kind="expand"),
                arguments={
                    "source": python_spec.ref.profile("transformed_dataset").dataframe,
                },
                outputs=[python_spec.feature.Feature(id="input_2")],
            ),
        ],
    )
    summary = python_spec.profile.Profile(
        id="summary",
        grain=[python_spec.Grain(id_dimension, "id")],
        assembly=[
            python_spec.actions.Operator(
                id="collapse_data",
                inputs=[python_spec.ref.feature("input_2")],
                function=python_spec.ref.function(analytics.aggregate, kind="collapse"),
                arguments={
                    "dataset": python_spec.ref.profile("target").dataframe,
                    "feature": python_spec.ref.feature("input_2").id,
                    "group_by": python_spec.ref.current_profile().grain.ids,
                    "output": python_spec.ref.feature("collapsed_feature").id,
                },
                outputs=[python_spec.feature.Feature(id="collapsed_feature")],
            )
        ],
    )
    spec_definition = spec.from_python(
        profiles=[source, target, summary],
        name="transforms_test",
    )

    ds_model = spec_definition.profiles["target"]
    assert set(ds_model.actions) == {"read", "expand_data"}
    assert {"target_value", "input_2"} <= set(ds_model.all_features)
    expand = ds_model.actions["expand_data"]
    assert expand.binding.function == "expand_data"
    assert expand.binding.args == {
        "source": "$profiles.transformed_dataset.dataframe",
    }
    assert expand.input_features == ["input_1"]
    collapse = spec_definition.profiles["summary"].actions["collapse_data"]
    assert collapse.binding.function == "aggregate"
    assert collapse.binding.args == {
        "dataset": "$profiles.target.dataframe",
        "feature": "$features.input_2.id",
        "group_by": "$profiles.@.grain.ids",
        "output": "$features.collapsed_feature.id",
    }
    assert collapse.output_features == ["id", "collapsed_feature"]
    assert spec_definition.functions["aggregate"].kind == "collapse"
