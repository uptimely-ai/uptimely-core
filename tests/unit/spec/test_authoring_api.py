import typing

import polars as pl
import pytest
from conftest import engine_for_plan

import uptimely as up
from uptimely.spec.python import bind, binding_conversion, ref, row_context


@up.function(kind="read")
def read_values() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "value": [10, 20]})


@up.function(kind="vectorize")
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


def test_root_authoring_api_compiles_and_executes() -> None:
    class CalculatedData(up.Dataset):
        id = "calculated_dataset"
        entity = "measurements"
        producers = [
            up.Action(
                id="read",
                function=read_values,
                arguments={},
                outputs=[up.Feature(name="value")],
            ),
            up.Action(
                id="double",
                function=double,
                arguments={
                    "dataset": up.ref.dataframe(),
                    "value": up.ref.column("value"),
                    "output": up.ref.output("doubled"),
                },
                outputs=[up.Feature(name="doubled")],
            ),
        ]

    declaration = up.Spec(
        dimensions=[up.Dimension(id="id", type="integer")],
        entities=[up.Entity(id="measurements", name="Measurements", dimensions=["id"])],
        datasets=[CalculatedData],
    )
    model = declaration.to_model()
    action = model.entities["measurements"].datasets["calculated_dataset"].actions["double"]
    assert action.input_features == ["value"]
    assert action.output_features == ["doubled"]
    assert action.binding.args == {
        "dataset": "$datasets.@.dataframe",
        "value": "$features.value",
        "output": "$features.doubled.id",
    }
    assert model.functions["double"].args["dataset"].type == "dataframe"
    assert model.functions["double"].args["value"].type == "string"
    assert model.functions["double"].args["output"].type == "string"

    execution_plan = up.Compiler().compile(model, features=["doubled"])
    execution = engine_for_plan(execution_plan, spec_definition=model).run()
    assert not execution.failures
    result = execution.datasets["calculated_dataset"].sort("id")
    assert result["doubled"].to_list() == [20, 40]


@pytest.mark.parametrize("name", [None, "telemetry"])
def test_dataframe_helper_matches_existing_selectors(name: str | None) -> None:
    expected = ref.current_dataset() if name is None else ref.dataset(name)
    assert up.ref.dataframe(name) == expected.dataframe
    assert binding_conversion.argument_definition(up.ref.dataframe(name)) == {"type": "dataframe"}


def test_column_and_output_helpers_preserve_document_values() -> None:
    assert up.ref.column("value") == ref.feature("value")
    output = up.ref.output("result")
    assert output.to_model() == ref.feature("result").id.to_model()
    assert binding_conversion.argument_definition(output) == {"type": "string"}


def test_global_parameter_and_feature_authoring() -> None:
    parameter = up.ref.parameter("asset_limit")
    feature = up.Feature("asset_limit").to_model()

    assert parameter == "$params.asset_limit"
    assert up.ref.source("telemetry_source") == "$params.telemetry_source"
    assert up.ref.sink("results_path") == "$params.results_path"
    assert feature.id == "asset_limit"


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

    def create_action() -> up.Action:
        return up.Action(
            id="calculate",
            function=ref.function("external:calculate", kind="vectorize"),
            arguments={"output": shapes[shape]},
            outputs=[up.Feature(name="result")] if declared else [],
        )

    if not declared:
        with pytest.raises(
            ValueError, match="Action 'calculate' references undeclared output 'result'"
        ):
            create_action()
    else:
        action = create_action()
        assert action.to_model().input_features == []
        assert action.to_model().output_features == ["result"]


def test_mutated_output_references_are_revalidated_on_conversion() -> None:
    action = up.Action(
        id="calculate",
        function=ref.function("external:calculate", kind="vectorize"),
        arguments={"output": up.ref.output("result")},
        outputs=[up.Feature(name="result")],
    )
    action.outputs.clear()
    with pytest.raises(ValueError, match="undeclared output 'result'"):
        action.to_model()
