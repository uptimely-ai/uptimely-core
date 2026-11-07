"""Bound-argument value, selector, and resolution contracts."""

import copy
import json

import pydantic
import pytest

from uptimely.spec import model, selectors
from uptimely.spec.python import assembly, ref


def _context() -> tuple[
    dict[str, list[str]],
    dict[str, dict[str, pydantic.BaseModel]],
]:
    return (
        {"telemetry": ["pump", "time"], "source": ["pump"]},
        {
            selectors.FEATURE_PREFIX: {
                "pressure": model.Feature(id="pressure", name="Pressure", unit="bar"),
            },
            selectors.PROFILE_PREFIX: {
                "telemetry": model.Profile(id="telemetry", description="Observations"),
            },
            selectors.DIMENSION_PREFIX: {
                "pump": model.Dimension(
                    id="pump",
                    resolutions={
                        "unit": model.Resolution(id="unit", key="pump_id", type="integer")
                    },
                ),
            },
        },
    )


def _resolve(
    argument: model.BindingArgument,
    profile_id: str = "telemetry",
    feature_id: str | None = "output",
) -> object:
    grain_keys_by_profile, resources = _context()
    return argument.resolve(profile_id, feature_id, grain_keys_by_profile, resources)


@pytest.mark.parametrize("value", [None, True, False, 0, 1.5, "literal", [], {}, {"x": [1, None]}])
def test_argument_serialization_preserves_json_value(value: pydantic.JsonValue) -> None:
    argument = model.BindingArgument(value)
    binding = model.Binding.model_validate({"function": "calculate", "args": {"value": value}})

    assert isinstance(binding.args["value"], model.BindingArgument)
    assert argument.model_dump() == value
    assert json.loads(argument.model_dump_json()) == value
    assert binding.model_dump() == {"function": "calculate", "args": {"value": value}}
    assert model.Binding.model_validate_json(binding.model_dump_json()) == binding
    assert type(argument.root) is type(value)


def test_argument_traversal_preserves_paths_order_and_duplicates() -> None:
    argument = model.BindingArgument(
        {
            "nested": ["$features.pressure.id", {"data": "$profiles.@.dataframe"}, 7],
            "duplicate": "$features.pressure",
            "empty": [],
        }
    )
    assert [(leaf.root, path) for leaf, path in argument.leaves_with_paths] == [
        ("$features.pressure.id", ("nested", 0)),
        ("$profiles.@.dataframe", ("nested", 1, "data")),
        (7, ("nested", 2)),
        ("$features.pressure", ("duplicate",)),
    ]
    assert argument.feature_references == ("pressure", "pressure")
    assert argument.inferred_feature_inputs == ("pressure",)
    assert argument.leaves_with_paths is argument.leaves_with_paths
    assert argument.references_with_paths is argument.references_with_paths
    binding = model.Binding(function="calculate", args={"config": argument})
    assert binding.args["config"] is argument
    assert binding.references_by_prefix[selectors.PROFILE_PREFIX] == (
        ("@", ("config", "nested", 1, "data")),
    )


def test_inferred_dependencies_exclude_metadata_and_deduplicate_after_resolution() -> None:
    argument = model.BindingArgument(
        [
            "$profiles.@.dataframe",
            "$profiles.telemetry",
            "$profiles.source.dataframe",
            "$profiles.source.dataframe",
            "$profiles.source.id",
            "$profiles.source.grain.ids",
            "$profiles.source.name",
            "$features.pressure.id",
            "$features.pressure",
            "$features.pressure",
            "$features.@",
        ]
    )
    assert argument.profile_dataframe_references == ("@", "telemetry", "source", "source")
    assert argument.profile_dependencies("telemetry") == ["telemetry", "source"]
    assert argument.inferred_feature_inputs == ("pressure",)
    binding = model.Binding(
        function="calculate",
        args={"nested": argument, "again": "$profiles.source.dataframe"},
    )
    assert binding.profile_dependencies("telemetry") == ["telemetry", "source"]
    assert binding.inferred_feature_inputs == ("pressure",)


def test_resolution_is_contextual_and_does_not_modify_bound_values() -> None:
    value = {
        "current": "$profiles.@.dataframe",
        "source_keys": "$profiles.source.grain.ids",
        "output": "$features.@.id",
        "metadata": ["$features.pressure.unit", "$profiles.@.description"],
        "resolution": [
            "$dimensions.pump.resolutions.unit",
            "$dimensions.pump.resolutions.unit.key",
            "$dimensions.pump.resolutions.unit.type",
        ],
        "literal": [True, 0, None, "ordinary.id", "$params.path", "$operators.@.fragment"],
    }
    argument = model.BindingArgument(value)
    assert _resolve(argument) == {
        "current": "telemetry",
        "source_keys": ["pump"],
        "output": "output",
        "metadata": ["bar", "Observations"],
        "resolution": ["unit", "pump_id", "integer"],
        "literal": value["literal"],
    }
    binding = model.Binding(function="calculate", args={"nested": argument})
    grain_keys_by_profile, resources = _context()
    assert binding.resolve_args(
        "telemetry",
        "output",
        grain_keys_by_profile,
        resources,
    ) == {"nested": argument.resolve("telemetry", "output", grain_keys_by_profile, resources)}
    current = model.BindingArgument(["$profiles.@.dataframe", "$features.@"])
    assert _resolve(current, "source", "second") == ["source", "second"]
    assert _resolve(current, "telemetry", None) == ["telemetry", "$features.@"]
    assert argument.root == value


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("$profiles.missing.grain.ids", "Cannot resolve grain keys"),
        ("$profiles.missing.name", "Cannot resolve resource metadata"),
        ("$features.pressure.unsupported", "Unsupported resource selector"),
        ("$features.pressure.dataframe", "Unsupported resource selector"),
        ("$dimensions.pump.grain.ids", "Unsupported resource selector"),
        ("$dimensions.pump.resolutions.missing.key", "Cannot resolve resolution"),
        ("$dimensions.pump.resolutions.unit.unsupported", "Unsupported resource selector"),
    ],
)
def test_unavailable_selectors_raise_explicit_errors(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _resolve(model.BindingArgument(value))


def test_grain_resolution_requires_context() -> None:
    with pytest.raises(ValueError, match="Cannot resolve grain keys for profile telemetry"):
        model.BindingArgument("$profiles.@.grain.ids").resolve("telemetry")


def test_nested_argument_types_follow_each_container_segment() -> None:
    argument = model.BindingArgument({"values": [1, 2]})
    assert list(argument.typed_values("object{str: array[integer]}")) == [
        (1, "integer"),
        (2, "integer"),
    ]
    assert list(argument.typed_values("object")) == [(1, "string"), (2, "string")]


def test_nested_pydantic_values_are_resolved_by_binding() -> None:
    class Config(pydantic.BaseModel):
        column: str

    raw = {"config": Config(column="$features.pressure")}
    grain_keys_by_profile, resources = _context()
    binding = model.Binding(function="calculate", args={"value": raw})

    assert binding.resolve_args(
        "telemetry",
        grain_keys_by_profile=grain_keys_by_profile,
        resources=resources,
    ) == {"value": {"config": {"column": "pressure"}}}


def test_operator_resolves_compute_arguments_using_its_output_context() -> None:
    operator = model.Operator(
        id="calculate",
        compute=model.Binding(function="calculate", args={"output": "$features.@"}),
        interface=model.Interface(outputs=["$features.pressure"]),
    )
    grain_keys_by_profile, resources = _context()

    assert operator.resolve_args(
        function_id="calculate",
        function_kind="vectorize",
        profile_id="telemetry",
        grain_keys_by_profile=grain_keys_by_profile,
        resources=resources,
        id_columns=["pump", "time"],
    ) == {"output": "pressure"}


def test_cached_views_do_not_change_equality_copy_or_round_trip() -> None:
    argument = model.BindingArgument({"columns": ["$features.pressure", "$profiles.@.dataframe"]})
    expected = model.BindingArgument(argument.model_dump())
    assert argument.profile_dependencies("telemetry") == ["telemetry"]
    assert argument.inferred_feature_inputs == ("pressure",)
    assert _resolve(argument) == {"columns": ["pressure", "telemetry"]}
    assert argument == expected
    assert expected == argument
    assert copy.deepcopy(argument) == expected
    assert model.BindingArgument.model_validate_json(argument.model_dump_json()) == argument
    assert argument != model.BindingArgument(None)
    assert argument != argument.root


@pytest.mark.parametrize("value", [object(), {"value": object()}, [object()]])
def test_non_json_bound_values_are_rejected(value: object) -> None:
    with pytest.raises(pydantic.ValidationError):
        model.BindingArgument.model_validate(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$profiles.@.dataframe", "dataframe"),
        ("$profiles.source.dataframe", "dataframe"),
        ("$profiles.@.grain.ids", "array[string]"),
        ("$profiles.source.id", "string"),
        ("$features.pressure.unit", "string"),
        ("$dimensions.pump.resolutions.unit.key", "string"),
        ("$operators.@.fragment", "dataframe"),
        ("$params.source.id", "string"),
        ("$features.pressure", None),
        ("$profiles.source", None),
        ("$params.source", None),
        ("ordinary.id", None),
        (None, None),
        ([], None),
    ],
)
def test_selector_type_shortcuts(value: pydantic.JsonValue, expected: str | None) -> None:
    argument = model.BindingArgument(value)
    assert argument.selector_value_type == expected
    assert argument.required_type("string") == expected
    nullable_expected = (
        "dataframe | null"
        if isinstance(value, str) and value.startswith("$profiles.") and expected == "dataframe"
        else expected
    )
    assert argument.required_type("dataframe | null") == nullable_expected


@pytest.mark.parametrize(
    ("value", "dataset", "fragment", "feature", "grain"),
    [
        ("$profiles.@.dataframe", True, False, False, False),
        ("$profiles.@", False, False, False, False),
        ("$profiles.@.id", False, False, False, False),
        ("$profiles.source.dataframe", False, False, False, False),
        ("$operators.@.fragment", False, True, False, False),
        ("$operators.other.fragment", False, False, False, False),
        ("$features.@.id", False, False, True, False),
        ("$features.@.name", False, False, True, False),
        ("$features.pressure", False, False, False, False),
        ("$profiles.source.grain.ids", False, False, False, True),
        (None, False, False, False, False),
    ],
)
def test_reference_predicates(
    value: pydantic.JsonValue, dataset: bool, fragment: bool, feature: bool, grain: bool
) -> None:
    argument = model.BindingArgument(value)
    assert argument.is_current_profile_dataframe is dataset
    assert argument.is_current_fragment is fragment
    assert argument.is_current_feature_reference is feature
    assert argument.is_grain_reference is grain


def test_binding_contract_comparison_and_typed_reference_views() -> None:
    function = model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns="dataframe",
        entrypoint="example:calculate",
        args={
            "data": model.Argument(id="data", type="dataframe"),
            "columns": model.Argument(id="columns", type="array[string]"),
        },
    )
    binding = model.Binding(
        function="calculate",
        args={
            "columns": ["$features.pressure.unit", "$features.@", "$profiles.@.grain.ids"],
            "unexpected": "$features.temperature",
        },
    )
    assert binding.argument_mismatches(function) == ({"data"}, {"unexpected"})
    assert [(leaf.root, kind) for leaf, kind in binding.typed_arguments(function)] == [
        ("$features.pressure.unit", "string"),
        ("$features.@", "string"),
        ("$profiles.@.grain.ids", "string"),
    ]
    assert [(leaf.root, path) for leaf, path in binding.metadata_references_with_paths] == [
        ("$features.pressure.unit", ("columns", 0)),
    ]
    assert [(leaf.root, path) for leaf, path in binding.grain_references_with_paths] == [
        ("$profiles.@.grain.ids", ("columns", 2)),
    ]
    assert binding.feature_references == ("pressure", "@", "temperature")
    assert binding.uses_current_feature
    assert binding.metadata_references_with_paths is binding.metadata_references_with_paths
    assert not model.Binding(function="calculate").uses_current_feature
    assert binding == model.Binding.model_validate(binding.model_dump())


def test_python_inference_uses_argument_facts_and_keeps_explicit_inputs_authoritative() -> None:
    binding = assembly.Binding(
        function=ref.function("calculation:calculate", kind="vectorize"),
        arguments={
            "config": [
                ref.feature("pressure"),
                "$features.temperature",
                ref.feature("pressure").id,
                ref.feature("output"),
                ref.feature("@"),
            ],
        },
    )
    inferred = assembly.Operator(
        id="calculate",
        interface=assembly.Interface(outputs=[]),
        compute=binding,
    )
    assert inferred.to_model().input_features == ["pressure", "temperature", "output"]
    explicit = assembly.Operator(
        id="calculate",
        interface=assembly.Interface(inputs=[], outputs=[]),
        compute=binding,
    )
    assert explicit.to_model().input_features == []
