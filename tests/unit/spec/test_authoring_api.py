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
        grain = [
            up.Grain(
                up.Dimension(
                    id="id",
                    resolutions=[up.Resolution(id="id", key="id", type="integer")],
                ),
                "id",
            )
        ]
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
                        "dataset": up.ref.dataframe(),
                        "value": up.ref.column("value"),
                        "output": up.ref.output("doubled"),
                    },
                ),
            ),
        ]

    declaration = up.Spec(profiles=[CalculatedData])
    model = declaration.to_model()
    action = model.profiles["calculated_profile"].actions["double"]
    assert action.input_features == ["value"]
    assert action.output_features == ["doubled"]
    assert action.binding.args == {
        "dataset": "$profiles.@.dataframe",
        "value": "$features.value",
        "output": "$features.doubled.id",
    }
    assert model.functions["double"].args["dataset"].type == "dataframe"
    assert model.functions["double"].args["value"].type == "string"
    assert model.functions["double"].args["output"].type == "string"

    execution_plan = up.Compiler().compile(model, features=["doubled"])
    execution = engine_for_plan(execution_plan, spec_definition=model).run()
    assert not execution.failures
    result = execution.main_frames["calculated_profile"].sort("id")
    assert result["doubled"].to_list() == [20, 40]


@pytest.mark.parametrize("name", [None, "telemetry"])
def test_dataframe_helper_matches_existing_selectors(name: str | None) -> None:
    expected = ref.current_profile() if name is None else ref.profile(name)
    assert up.ref.dataframe(name) == expected.dataframe
    assert binding_conversion.argument_definition(up.ref.dataframe(name)) == {"type": "dataframe"}


def test_column_and_output_helpers_preserve_document_values() -> None:
    assert up.ref.column("value") == ref.feature("value")
    output = up.ref.output("result")
    assert output.to_model() == ref.feature("result").id.to_model()
    assert binding_conversion.argument_definition(output) == {"type": "string"}


def test_global_parameter_and_feature_authoring() -> None:
    parameter = up.ref.parameter("asset_limit")
    feature = up.Feature(id="asset_limit").to_model()

    assert parameter == "$params.asset_limit"
    assert up.ref.source("telemetry_source") == "$params.telemetry_source"
    assert up.ref.sink("results_path") == "$params.results_path"
    assert feature.id == "asset_limit"
    assert feature.name == "Asset Limit"


def test_profile_features_attributes_can_be_action_outputs() -> None:
    class Features(up.FeatureSet):
        value = up.Feature(id="value", type="float")

    features = Features()
    action = up.Operator(
        id="read",
        interface=up.Interface(
            outputs=[features.value],
        ),
        compute=up.Binding(
            function=read_values,
            arguments={},
        ),
    )

    assert action.to_model().output_features == ["value"]
    assert Features.value.to_model().type == "float"


@pytest.mark.parametrize("shape", ["direct", "list", "tuple", "dict", "bind", "context"])
@pytest.mark.parametrize("declared", [False, True])
def test_output_references_validate_nested_arguments(shape: str, declared: bool) -> None:
    output = up.ref.output("result")
    shapes: dict[str, typing.Any] = {
        "direct": output,
        "list": [output],
        "tuple": (output,),
        "dict": {"name": output},
        "bind": bind.bind(ref.function("external:identity"), value=output),
        "context": row_context.rows(output, before=1),
    }

    def create_action() -> up.Operator:
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

    if not declared:
        with pytest.raises(
            ValueError, match="Operator 'calculate' references undeclared output 'result'"
        ):
            create_action()
    else:
        action = create_action()
        assert action.to_model().input_features == []
        assert action.to_model().output_features == ["result"]


def test_mutated_output_references_are_revalidated_on_conversion() -> None:
    action = up.Operator(
        id="calculate",
        interface=up.Interface(
            outputs=[up.Feature(id="result")],
        ),
        compute=up.Binding(
            function=ref.function("external:calculate", kind="vectorize"),
            arguments={"output": up.ref.output("result")},
        ),
    )
    action.interface.outputs.clear()
    with pytest.raises(ValueError, match="undeclared output 'result'"):
        action.to_model()
