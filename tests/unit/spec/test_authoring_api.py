import typing

import polars as pl
import pytest
from support import execution as execution_support

import uptimely as up
from uptimely.spec.python import bind, binding_conversion, ref, row_context


@up.function(kind="read")
def read_values() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "value": [10, 20]})


@up.function(kind="vectorize")
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


def test_root_authoring_api_compiles_and_executes(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    class CalculatedData(up.Profile):
        id = "calculated_profile"
        id_dimension = up.Dimension(
            id="id",
            resolutions=[up.Resolution(id="id", key="id", type="integer")],
        )
        grain = [id_dimension.resolution("id")]
        assembly = [
            up.Operator(
                id="read",
                interface=up.Interface(outputs=[up.Feature(id="value")]),
                compute=up.Binding(function=read_values),
            ),
            up.Operator(
                id="double",
                interface=up.Interface(outputs=[up.Feature(id="doubled")]),
                compute=up.Binding(
                    function=double,
                    arguments={
                        "dataset": up.ref.dataset(),
                        "value": up.ref.feature("value"),
                        "output": up.ref.feature("doubled"),
                    },
                ),
            ),
        ]

    declaration = up.Spec(profiles=[CalculatedData])
    model = declaration.to_model()
    operator = model.profiles["calculated_profile"].assembly["double"]
    assert operator.input_features == ["value"]
    assert operator.output_features == ["doubled"]
    assert operator.compute.model_dump()["args"] == {
        "dataset": "$profiles.@.dataset",
        "value": "$features.value",
        "output": "$features.doubled",
    }
    assert model.functions["double"].args["dataset"].type == "dataframe"
    assert model.functions["double"].args["value"].type == "string"
    assert model.functions["double"].args["output"].type == "string"

    execution_plan = up.Compiler().compile(model, features=["doubled"])
    execution = engine_for_plan(execution_plan, spec_definition=model).run()
    assert not execution.failures
    result = execution.datasets["calculated_profile"].sort("id")
    assert result["doubled"].to_list() == [20, 40]


@pytest.mark.parametrize("name", [None, "telemetry"])
def test_dataframe_helper_matches_existing_selectors(name: str | None) -> None:
    expected = ref.profile() if name is None else ref.profile(name)
    assert up.ref.dataset(name) == expected.dataset
    assert binding_conversion.argument_definition(up.ref.dataset(name)) == {"type": "dataframe"}


def test_feature_reference_defaults_to_id_binding() -> None:
    assert up.ref.feature("value") == ref.feature("value")
    output = up.ref.feature("result")
    assert output.to_model() == "$features.result"
    assert binding_conversion.argument_definition(output) == {"type": "string"}


def test_global_parameter_and_feature_authoring() -> None:
    parameter = up.ref.params("asset_limit")
    feature = up.Feature(id="asset_limit").to_model()

    assert parameter == up.Params("asset_limit")
    assert parameter.to_model() == "$params.asset_limit"
    assert up.ref.params("telemetry_source").to_model() == "$params.telemetry_source"
    assert up.ref.params("results_path").to_model() == "$params.results_path"
    assert feature.id == "asset_limit"
    assert feature.name == "Asset Limit"


def test_profile_features_attributes_can_be_operator_outputs() -> None:
    class Features(up.FeatureSet):
        value = up.Feature(type="float")

    features = Features()
    operator = up.Operator(
        id="read",
        interface=up.Interface(
            outputs=[features.value],
        ),
        compute=up.Binding(
            function=read_values,
            arguments={},
        ),
    )

    assert operator.to_model().output_features == ["value"]
    assert features.value.id == "value"
    assert features.value.name == "Value"
    assert Features.value.to_model().type == "float"


def test_feature_set_preserves_explicit_feature_id() -> None:
    class Features(up.FeatureSet):
        display_value = up.Feature(id="value", type="float")

    assert Features.display_value.id == "value"


@pytest.mark.parametrize("shape", ["direct", "list", "tuple", "dict", "bind", "context"])
@pytest.mark.parametrize("declared", [False, True])
def test_feature_roles_follow_interface_in_nested_arguments(shape: str, declared: bool) -> None:
    output = up.ref.feature("result")
    shapes: dict[str, typing.Any] = {
        "direct": output,
        "list": [output],
        "tuple": (output,),
        "dict": {"name": output},
        "bind": bind.bind(ref.function("external:identity"), value=output),
        "context": row_context.rows(output, before=1),
    }

    def create_operator() -> up.Operator:
        return up.Operator(
            id="calculate",
            interface=up.Interface(
                outputs=[up.Feature(id="result")] if declared else [],
            ),
            compute=up.Binding(
                function=ref.function("external:calculate", kind="vectorize"),
                arguments={"output": shapes[shape]},
            ),
        )

    operator = create_operator()
    assert operator.to_model().input_features == ([] if declared else ["result"])
    assert operator.to_model().output_features == (["result"] if declared else [])


def test_mutated_interface_updates_inferred_input_roles() -> None:
    operator = up.Operator(
        id="calculate",
        interface=up.Interface(
            outputs=[up.Feature(id="result")],
        ),
        compute=up.Binding(
            function=ref.function("external:calculate", kind="vectorize"),
            arguments={"output": up.ref.feature("result")},
        ),
    )
    operator.interface.outputs.clear()
    assert operator.to_model().input_features == ["result"]
