"""Checks for class-based and programmatic Python declarations."""

import dataclasses
import typing

import pytest

from uptimely.spec import functions
from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, dimension, entity, ref, row_context


@authoring.function(kind="vectorize")
def must_not_execute(values: list[str], output: str) -> None:
    raise AssertionError("Assembly executed the implementation")


@authoring.function(kind="vectorize")
def calculate(value: str) -> str:
    return value


def test_action_is_the_only_public_work_declaration_name() -> None:
    assert authoring.Action.__name__ == "Action"
    assert not hasattr(authoring, "FunctionCall")
    assert not hasattr(authoring, "Mapping")
    assert not hasattr(authoring, "FunctionMapping")
    assert not hasattr(authoring, "action")


def test_named_output_list_preserves_order_and_canonical_json_ids() -> None:
    declaration = authoring.Dataset(
        id="example",
        producers=[
            authoring.Action(
                id="read",
                function=ref.function("reader:read", kind="read"),
                arguments={},
                outputs=[
                    authoring.Feature(name="temperature", type="float", unit="C"),
                    authoring.Feature(name="pump", type="string"),
                ],
            )
        ],
    )

    canonical = declaration.to_model()
    assert list(canonical.features) == ["temperature", "pump"]
    assert canonical.features["temperature"].id == "temperature"
    assert canonical.actions["read"].output_features == ["temperature", "pump"]
    payload = conversion.to_dict(datasets=[declaration])
    exported = payload["entities"]["entity"]["datasets"]["example"]
    assert exported["features"]["temperature"] == {
        "type": "float",
        "unit": "C",
        "description": None,
    }
    assert exported["actions"]["read"]["features"]["outputs"] == [
        "$features.temperature",
        "$features.pump",
    ]


def test_mapping_rejects_duplicate_output_names() -> None:
    with pytest.raises(ValueError, match="output feature names must not repeat"):
        authoring.Action(
            id="action",
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
        producers = [
            authoring.Action(
                id="result",
                function=must_not_execute,
                arguments={
                    "values": [ref.feature("temperature"), ref.feature("temperature")],
                    "output": ref.feature("result").id,
                },
                outputs=[authoring.Feature(name="result", type="float")],
            )
        ]

    declaration = Example()
    action = declaration.producers[0]
    model = declaration.to_model().actions["result"]

    assert model.id == "result"
    assert model.input_features == ["temperature"]
    assert action.arguments == {
        "values": [ref.feature("temperature"), ref.feature("temperature")],
        "output": ref.feature("result").id,
    }
    assert action.bound_arguments() == action.arguments
    assert model.binding.args["output"] == "$features.result.id"
    assert action.outputs[0].name == "result"
    assert action.outputs[0].type == "float"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "missing a required argument: 'feature'"),
        ({"feature": "temperature", "unknown": 1}, "unexpected keyword argument 'unknown'"),
    ],
)
def test_assembly_reports_invalid_arguments(arguments: dict[str, object], message: str) -> None:
    @authoring.function(kind="write")
    def implementation(feature: str) -> None:
        pass

    class Example(authoring.Dataset):
        id = "example"
        publishers = [
            authoring.Action(
                id="invalid",
                function=implementation,
                arguments=arguments,
                outputs=[],
            )
        ]

    with pytest.raises(TypeError, match="Dataset 'example', action 'invalid'") as error:
        Example().to_model()
    assert message in str(error.value)


@pytest.mark.parametrize("identifier", ["result", "asset"])
def test_duplicate_producers_are_rejected(identifier: str) -> None:
    class Example(authoring.Dataset):
        id = "example"
        keys = (dimension.Dimension(id="asset", type="string"),)
        producers = [
            authoring.Action(
                id="first",
                function=ref.function(
                    "test_declarative_authoring:implementation", kind="vectorize"
                ),
                arguments={"output": ref.feature(identifier).id},
                outputs=[authoring.Feature(name=identifier, type="float")],
            )
        ]
        producers = [*producers, dataclasses.replace(producers[0], id="second")]

    with pytest.raises(ValueError, match="'first' and 'second'"):
        Example().to_model()


def test_dataset_subclasses_inherit_and_replace_collections() -> None:
    first = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[authoring.Feature(name="value", type="float")],
    )
    replacement = authoring.Action(
        id="read",
        function=ref.function("reader:replacement", kind="read"),
        arguments={},
        outputs=[authoring.Feature(name="value", type="integer")],
    )
    sink = authoring.Action(
        id="write",
        function=ref.function("writer:write", kind="write"),
        arguments={"column": ref.feature("value")},
        outputs=[],
    )

    class Base(authoring.Dataset):
        id = "base"
        description = "Inherited metadata"
        producers = [first]
        publishers = [sink]

    class Derived(Base):
        id = "derived"
        producers = [replacement]

    base = Base()
    derived = Derived()
    assert base.producers == [first]
    assert derived.producers == [replacement]
    assert derived.publishers == [sink]
    assert list(derived.to_model().actions) == ["read", "write"]
    assert derived.to_model().description == "Inherited metadata"
    assert derived.to_model().features["value"].type == "integer"
    assert set(derived.function_catalog()) == {"replacement", "write"}


def test_dataset_requires_identifier() -> None:
    with pytest.raises((TypeError, ValueError), match="id"):
        authoring.Dataset().to_model()


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
        producers = [
            authoring.Action(
                id="values",
                function=ref.function("reader:values", kind="read"),
                arguments={},
                outputs=[authoring.Feature(name="value", type="float")],
            )
        ]

    model = Example().to_model()

    assert model.features["asset"].type == "string"
    assert model.features["asset"].description == "Asset key"
    assert model.actions["values"].output_features == ["asset", "value"]


def test_nested_arguments_infer_inputs_without_identifier_selectors() -> None:
    action = authoring.Action(
        id="result",
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
    model = action.to_model()
    assert action.inputs is None
    assert model.input_features == ["first", "second"]
    assert model.row_context.before.rows == 2
    assert model.binding.args["configuration"] == {
        "columns": ["$features.first", "$features.second", "$features.first"],
        "output": "$features.result.id",
        "key": "$dimensions.asset.id",
    }


def test_programmatic_dataset_preserves_mapping_names_and_function_overrides() -> None:
    action = authoring.Action(
        id="named",
        function=ref.function("calculation:calculate", kind="vectorize"),
        function_id="custom",
        arguments={"column": ref.feature("inferred")},
        inputs=[ref.feature("explicit")],
        outputs=[authoring.Feature(name="result", type="float")],
    )
    declaration = authoring.Dataset(id="example", producers=[action])

    assert declaration.producers == [action]
    assert action.reference.entrypoint == "calculation:calculate"
    assert action.catalog_id == "custom"
    assert declaration.to_model().actions["named"].input_features == ["explicit"]
    assert declaration.to_model().actions["named"].binding.function == "custom"
    assert set(declaration.function_catalog()) == {"custom"}


def test_dataset_dimension_selector_is_preserved_and_typed_in_python_specs() -> None:
    identifier = dimension.Dimension(id="asset", type="string")
    declaration = authoring.Dataset(
        id="example",
        producers=[
            authoring.Action(
                id="read",
                function=ref.function("reader:read", kind="read"),
                arguments={
                    "keys": ref.current_dataset().dimensions.ids,
                    "source_keys": ref.dataset("source").dimensions.ids,
                },
                outputs=[authoring.Feature(name="value", type="float")],
            )
        ],
    )

    model = declaration.to_model()
    catalog = declaration.function_catalog()
    assert model.actions["read"].binding.args["keys"] == "$datasets.@.dimensions.ids"
    assert model.actions["read"].binding.args["source_keys"] == "$datasets.source.dimensions.ids"
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
        payload["entities"]["entity"]["datasets"]["example"]["actions"]["read"]["binding"]["args"][
            "keys"
        ]
        == "$datasets.@.dimensions.ids"
    )
    assert payload["functions"]["read"]["args"]["keys"]["type"] == "array[string]"


@pytest.mark.parametrize("required", ["id", "function", "arguments", "outputs"])
def test_mapping_constructor_requires_explicit_fields(required: str) -> None:
    arguments = {
        "id": "read",
        "function": ref.function("reader:read", kind="read"),
        "arguments": {},
        "outputs": [],
    }
    del arguments[required]
    with pytest.raises(TypeError, match=required):
        authoring.Action(**arguments)


def test_mapping_requires_function_kind_metadata() -> None:
    with pytest.raises(ValueError, match="Function kind is required"):
        authoring.Action(id="action", function="reader:read", arguments={}, outputs=[])


def test_kind_annotation_is_inferred_without_wrapping_function() -> None:
    declaration = authoring.Action(
        id="declaration",
        function=calculate,
        arguments={"value": "input"},
        outputs=[],
    )

    assert declaration.function is calculate
    assert declaration.kind == "vectorize"
    assert declaration.function_catalog()["calculate"].kind == "vectorize"


def test_action_export_uses_its_identifier() -> None:
    action = authoring.Action(
        id="action", function=ref.function("reader:read", kind="read"), arguments={}, outputs=[]
    )
    assert action.to_model().id == "action"


@pytest.mark.parametrize("identifier", ["", " ", None, 1])
def test_action_rejects_invalid_identifiers(identifier: typing.Any) -> None:
    with pytest.raises(ValueError, match="Action requires a non-empty id"):
        authoring.Action(
            id=identifier,
            function=ref.function("reader:read", kind="read"),
            arguments={},
            outputs=[],
        )


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
@pytest.mark.parametrize("collection", ["producers", "publishers", "pipelines"])
def test_action_collection_enforces_function_kind(
    kind: functions.FunctionKind, collection: str
) -> None:
    action = authoring.Action(
        id="work",
        function=ref.function("implementation:work", kind=kind),
        arguments={},
        outputs=[],
    )
    declarations = {
        "producers": [action] if collection == "producers" else [],
        "publishers": [action] if collection == "publishers" else [],
        "pipelines": [action] if collection == "pipelines" else [],
    }
    expected_collection = {"write": "publishers", "escape": "pipelines"}.get(kind, "producers")
    if collection != expected_collection:
        with pytest.raises(ValueError, match=f"kind '{kind}' is not allowed in {collection}"):
            authoring.Dataset(id="example", **declarations)
        return

    declaration = authoring.Dataset(id="example", **declarations)
    assert declaration.to_model().actions["work"] == action.to_model()
    assert declaration.function_catalog()["work"].kind == kind


@pytest.mark.parametrize("collection", ["producers", "publishers", "pipelines"])
@pytest.mark.parametrize("invalid", [{}, "invalid", [object()], [None]])
def test_action_collections_reject_invalid_values(collection: str, invalid: typing.Any) -> None:
    with pytest.raises(TypeError, match=f"{collection} must (be a sequence of|contain) Actions"):
        authoring.Dataset(id="example", **{collection: invalid})


@pytest.mark.parametrize("second_kind", ["read", "write", "escape"])
def test_action_ids_are_unique_across_collections(second_kind: functions.FunctionKind) -> None:
    first = authoring.Action(
        id="duplicate",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )
    second = dataclasses.replace(
        first, function=ref.function("implementation:work", kind=second_kind)
    )
    with pytest.raises(ValueError, match="Dataset 'example' has duplicate action ID 'duplicate'"):
        authoring.Dataset(
            id="example",
            producers=[first, second] if second_kind == "read" else [first],
            publishers=[second] if second_kind == "write" else [],
            pipelines=[second] if second_kind == "escape" else [],
        )


def test_collection_defaults_and_inherited_lists_are_not_shared_between_instances() -> None:
    read = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )

    class Base(authoring.Dataset):
        id = "base"
        producers = [read]

    first = Base()
    second = Base()
    assert isinstance(first.producers, list)
    assert isinstance(first.publishers, list)
    assert isinstance(first.pipelines, list)
    first.producers.clear()
    assert second.producers == Base.producers == [read]
    assert first.publishers is not second.publishers
    assert first.pipelines is not second.pipelines
    assert Base(producers=[]).producers == []

    supplied = [read]
    constructed = authoring.Dataset(id="constructed", producers=supplied)
    supplied.clear()
    assert constructed.producers == [read]


def test_subclasses_can_explicitly_extend_or_clear_inherited_collections() -> None:
    read = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )

    class Base(authoring.Dataset):
        id = "base"
        producers = [read]

    class Extended(Base):
        producers = [*Base.producers, dataclasses.replace(read, id="another_read")]

    class Empty(Base):
        producers = []

    assert list(Extended().to_model().actions) == ["read", "another_read"]
    assert Empty().to_model().actions == {}
    assert Base.producers == [read]


def test_conversion_revalidates_modified_action_collections() -> None:
    declaration = authoring.Dataset(id="example")
    declaration.producers = [
        authoring.Action(
            id="write",
            function=ref.function("writer:write", kind="write"),
            arguments={},
            outputs=[],
        )
    ]
    with pytest.raises(ValueError, match="not allowed in producers"):
        declaration.to_model()
    with pytest.raises(ValueError, match="not allowed in producers"):
        declaration.function_catalog()


def test_all_collections_preserve_dependencies_and_canonical_mapping_ids() -> None:
    class Example(authoring.Dataset):
        id = "example"
        producers = [
            authoring.Action(
                id="calculate",
                function=ref.function("implementation:calculate", kind="vectorize"),
                arguments={"column": ref.feature("pipeline_result")},
                outputs=[authoring.Feature(name="result")],
            )
        ]
        publishers = [
            authoring.Action(
                id="publish",
                function=ref.function("implementation:publish", kind="write"),
                arguments={"column": ref.feature("result")},
                outputs=[],
            )
        ]
        pipelines = [
            authoring.Action(
                id="custom_work",
                function=ref.function("implementation:custom_work", kind="escape"),
                arguments={},
                inputs=[ref.feature("external_input")],
                outputs=[authoring.Feature(name="pipeline_result")],
            )
        ]

    declaration = Example()
    model = declaration.to_model()
    assert list(model.actions) == ["calculate", "publish", "custom_work"]
    assert model.actions["calculate"].input_features == ["pipeline_result"]
    assert model.actions["publish"].input_features == ["result"]
    assert model.actions["custom_work"].input_features == ["external_input"]
    payload = conversion.to_dict(datasets=[declaration])
    exported = payload["entities"]["entity"]["datasets"]["example"]
    assert "producers" not in exported
    assert "publishers" not in exported
    assert "pipelines" not in exported
    assert set(exported["actions"]) == {"calculate", "publish", "custom_work"}
    assert set(exported["features"]) == {"result", "pipeline_result"}


def test_model_collects_dataset_classes_in_registry_order() -> None:
    class First(authoring.Dataset):
        id = "first"

    class Second(authoring.Dataset):
        id = "second"

    declarations = authoring.Model(datasets=[First, Second]).to_declarations()
    assert list(declarations) == ["first", "second"]
    assert isinstance(declarations["first"], First)
    assert isinstance(declarations["second"], Second)
