"""Checks for class-based and programmatic Python declarations."""

import pytest

from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, dimension, entity, ref, row_context


@authoring.kind("vectorize")
def must_not_execute(values: list[str], output: str) -> None:
    raise AssertionError("Assembly executed the implementation")


@authoring.kind("vectorize")
def calculate(value: str) -> str:
    return value


def test_function_mapping_is_the_only_public_mapping_declaration_name() -> None:
    assert authoring.FunctionMapping.__name__ == "FunctionMapping"
    assert not hasattr(authoring, "FunctionCall")
    assert not hasattr(authoring, "Mapping")


def test_named_output_list_preserves_order_and_canonical_json_ids() -> None:
    declaration = authoring.Dataset(
        id="example",
        mappings={
            "read": authoring.FunctionMapping(
                function=ref.function("reader:read", kind="read"),
                arguments={},
                outputs=[
                    authoring.Feature(name="temperature", type="float", unit="C"),
                    authoring.Feature(name="pump", type="string"),
                ],
            ),
        },
    )

    canonical = declaration.to_model()
    assert list(canonical.features) == ["temperature", "pump"]
    assert canonical.features["temperature"].id == "temperature"
    assert canonical.mappings["read"].output_features == ["temperature", "pump"]
    payload = conversion.to_dict(datasets=[declaration])
    exported = payload["entities"]["entity"]["datasets"]["example"]
    assert exported["features"]["temperature"] == {
        "type": "float",
        "unit": "C",
        "description": None,
    }
    assert exported["mappings"]["read"]["features"]["outputs"] == [
        "$features.temperature",
        "$features.pump",
    ]


def test_mapping_rejects_duplicate_output_names() -> None:
    with pytest.raises(ValueError, match="output feature names must not repeat"):
        authoring.FunctionMapping(
            function=ref.function("reader:read", kind="read"),
            arguments={},
            outputs=[
                authoring.Feature(name="temperature"),
                authoring.Feature(name="temperature"),
            ],
        )


def test_assembly_collects_inputs_without_executing_implementation() -> None:
    class Example(authoring.Dataset):
        id = "example"
        result = authoring.FunctionMapping(
            function=must_not_execute,
            arguments={
                "values": [ref.feature("temperature"), ref.feature("temperature")],
                "output": ref.feature("result").id,
            },
            outputs=[authoring.Feature(name="result", type="float")],
        )

    declaration = Example()
    mapping = declaration.mappings["result"]
    model = declaration.to_model().mappings["result"]

    assert model.id == "result"
    assert model.input_features == ["temperature"]
    assert mapping.arguments == {
        "values": [ref.feature("temperature"), ref.feature("temperature")],
        "output": ref.feature("result").id,
    }
    assert mapping.bound_arguments() == mapping.arguments
    assert model.binding.args["output"] == "$features.result.id"
    assert mapping.outputs[0].name == "result"
    assert mapping.outputs[0].type == "float"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "missing a required argument: 'feature'"),
        ({"feature": "temperature", "unknown": 1}, "unexpected keyword argument 'unknown'"),
    ],
)
def test_assembly_reports_invalid_arguments(arguments: dict[str, object], message: str) -> None:
    @authoring.kind("write")
    def implementation(feature: str) -> None:
        pass

    class Example(authoring.Dataset):
        id = "example"
        invalid = authoring.FunctionMapping(
            function=implementation,
            arguments=arguments,
            outputs=[],
        )

    with pytest.raises(TypeError, match="Dataset 'example', mapping 'invalid'") as error:
        Example().to_model()
    assert message in str(error.value)


@pytest.mark.parametrize("identifier", ["result", "asset"])
def test_duplicate_producers_are_rejected(identifier: str) -> None:
    class Example(authoring.Dataset):
        id = "example"
        keys = (dimension.Dimension(id="asset", type="string"),)
        first = authoring.FunctionMapping(
            function=ref.function("test_declarative_authoring:implementation", kind="vectorize"),
            arguments={"output": ref.feature(identifier).id},
            outputs=[authoring.Feature(name=identifier, type="float")],
        )
        second = first

    with pytest.raises(ValueError, match="'first' and 'second'"):
        Example().to_model()


def test_dataset_subclasses_inherit_and_override_named_mappings() -> None:
    first = authoring.FunctionMapping(
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[authoring.Feature(name="value", type="float")],
    )
    replacement = authoring.FunctionMapping(
        function=ref.function("reader:replacement", kind="read"),
        arguments={},
        outputs=[authoring.Feature(name="value", type="integer")],
    )
    sink = authoring.FunctionMapping(
        function=ref.function("writer:write", kind="write"),
        arguments={"column": ref.feature("value")},
        outputs=[],
    )

    class Base(authoring.Dataset):
        id = "base"
        description = "Inherited metadata"
        read = first

    class Derived(Base):
        id = "derived"
        read = replacement
        write = sink

    base = Base()
    derived = Derived()
    assert base.mappings == {"read": first}
    assert derived.mappings == {"read": replacement, "write": sink}
    assert list(derived.to_model().mappings) == ["read", "write"]
    assert derived.to_model().description == "Inherited metadata"
    assert derived.to_model().features["value"].type == "integer"
    assert set(derived.function_catalog()) == {"replacement", "write"}


def test_dataset_requires_identifier() -> None:
    with pytest.raises((TypeError, ValueError), match="id"):
        authoring.Dataset().to_model()


@pytest.mark.parametrize("kind", ["read", "collapse"])
def test_dataset_keys_supply_dimension_metadata(kind: str) -> None:
    identifier = dimension.Dimension(id="asset", type="string", description="Asset key")

    class Example(authoring.Dataset):
        id = "example"
        keys = (identifier,)
        values = authoring.FunctionMapping(
            function=ref.function("reader:values", kind=kind),
            arguments={},
            outputs=[authoring.Feature(name="value", type="float")],
        )

    model = Example().to_model()
    assert model.features["asset"].type == "string"
    assert model.features["asset"].description == "Asset key"
    assert model.mappings["values"].output_features == ["asset", "value"]
    assert Example().keys == (identifier,)


def test_dataset_entity_supplies_dimension_metadata() -> None:
    identifier = dimension.Dimension(id="asset", type="string", description="Asset key")
    owner = entity.Entity(
        id="assets",
        name="Assets",
        dimensions=[identifier],
    )

    class Example(authoring.Dataset):
        id = "example"
        entity = owner
        values = authoring.FunctionMapping(
            function=ref.function("reader:values", kind="read"),
            arguments={},
            outputs=[authoring.Feature(name="value", type="float")],
        )

    model = Example().to_model()

    assert model.features["asset"].type == "string"
    assert model.features["asset"].description == "Asset key"
    assert model.mappings["values"].output_features == ["asset", "value"]


def test_nested_arguments_infer_inputs_without_identifier_selectors() -> None:
    mapping = authoring.FunctionMapping(
        function=ref.function("calculation:calculate", kind="vectorize"),
        arguments={
            "configuration": {
                "columns": [
                    ref.feature("first"),
                    row_context.rows(ref.feature("second"), before=2),
                    ref.feature("first"),
                ],
                "output": ref.feature("result").id,
                "key": ref.dimension("asset").id,
            }
        },
        outputs=[authoring.Feature(name="result", type="float")],
    )
    model = mapping.to_model("result")
    assert mapping.inputs is None
    assert model.input_features == ["first", "second"]
    assert model.row_context.before.rows == 2
    assert model.binding.args["configuration"] == {
        "columns": ["$features.first", "$features.second", "$features.first"],
        "output": "$features.result.id",
        "key": "$dimensions.asset.id",
    }


def test_programmatic_dataset_preserves_mapping_names_and_function_overrides() -> None:
    mapping = authoring.FunctionMapping(
        function=ref.function("calculation:calculate", kind="vectorize"),
        function_id="custom",
        arguments={"column": ref.feature("inferred")},
        inputs=[ref.feature("explicit")],
        outputs=[authoring.Feature(name="result", type="float")],
    )
    declaration = authoring.Dataset(id="example", mappings={"named": mapping})

    assert declaration.mappings == {"named": mapping}
    assert mapping.reference.entrypoint == "calculation:calculate"
    assert mapping.catalog_id == "custom"
    assert declaration.to_model().mappings["named"].input_features == ["explicit"]
    assert declaration.to_model().mappings["named"].binding.function == "custom"
    assert set(declaration.function_catalog()) == {"custom"}


def test_dataset_keys_can_be_shared_by_read_mappings() -> None:
    identifier = dimension.Dimension(id="asset", type="string")

    class Example(authoring.Dataset):
        id = "example"
        keys = (identifier,)
        first = authoring.FunctionMapping(
            function=ref.function("reader:first", kind="read"),
            arguments={},
            outputs=[authoring.Feature(name="first_value", type="float")],
        )
        second = authoring.FunctionMapping(
            function=ref.function("reader:second", kind="read"),
            arguments={},
            outputs=[authoring.Feature(name="second_value", type="float")],
        )

    model = Example().to_model()
    assert set(model.features) == {"asset", "first_value", "second_value"}
    assert model.mappings["first"].output_features == ["asset", "first_value"]
    assert model.mappings["second"].output_features == ["asset", "second_value"]


def test_dataset_dimension_selector_is_preserved_and_typed_in_python_specs() -> None:
    identifier = dimension.Dimension(id="asset", type="string")
    declaration = authoring.Dataset(
        id="example",
        keys=(identifier,),
        mappings={
            "read": authoring.FunctionMapping(
                function=ref.function("reader:read", kind="read"),
                arguments={
                    "keys": ref.current_dataset().dimensions.ids,
                    "source_keys": ref.dataset("source").dimensions.ids,
                },
                outputs=[authoring.Feature(name="value", type="float")],
            )
        },
    )

    model = declaration.to_model()
    catalog = declaration.function_catalog()
    assert model.mappings["read"].binding.args["keys"] == "$datasets.@.dimensions.ids"
    assert model.mappings["read"].binding.args["source_keys"] == "$datasets.source.dimensions.ids"
    assert catalog["read"].args["keys"].type == "array[string]"
    assert catalog["read"].args["source_keys"].type == "array[string]"

    owner = entity.Entity(
        id="entity",
        name="Entity",
        dimensions=[identifier],
        datasets=[declaration],
    )
    payload = conversion.to_dict(entities=[owner])
    assert (
        payload["entities"]["entity"]["datasets"]["example"]["mappings"]["read"]["binding"]["args"][
            "keys"
        ]
        == "$datasets.@.dimensions.ids"
    )
    assert payload["functions"]["read"]["args"]["keys"]["type"] == "array[string]"


@pytest.mark.parametrize("required", ["function", "arguments", "outputs"])
def test_mapping_constructor_requires_explicit_fields(required: str) -> None:
    arguments = {
        "function": ref.function("reader:read", kind="read"),
        "arguments": {},
        "outputs": [],
    }
    del arguments[required]
    with pytest.raises(TypeError, match=required):
        authoring.FunctionMapping(**arguments)


def test_mapping_requires_function_kind_metadata() -> None:
    with pytest.raises(ValueError, match="annotated with @kind"):
        authoring.FunctionMapping(function="reader:read", arguments={}, outputs=[])


def test_kind_annotation_is_inferred_without_wrapping_function() -> None:
    declaration = authoring.FunctionMapping(
        function=calculate,
        arguments={"value": "input"},
        outputs=[],
    )

    assert declaration.function is calculate
    assert declaration.kind == "vectorize"
    assert declaration.function_catalog()["calculate"].kind == "vectorize"


def test_mapping_export_requires_explicit_identifier() -> None:
    mapping = authoring.FunctionMapping(
        function=ref.function("reader:read", kind="read"), arguments={}, outputs=[]
    )
    with pytest.raises(TypeError, match="identifier"):
        mapping.to_model()


def test_model_collects_dataset_classes_in_registry_order() -> None:
    class First(authoring.Dataset):
        id = "first"

    class Second(authoring.Dataset):
        id = "second"

    declarations = authoring.Model(datasets=[First, Second]).to_declarations()
    assert list(declarations) == ["first", "second"]
    assert isinstance(declarations["first"], First)
    assert isinstance(declarations["second"], Second)
