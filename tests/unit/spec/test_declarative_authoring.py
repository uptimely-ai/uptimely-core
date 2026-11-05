"""Checks for class-based and programmatic Python declarations."""

import dataclasses
import logging
import typing

import pytest

from uptimely.spec import functions
from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, dimension, ref, row_context, validation


@pytest.mark.parametrize("declared", [False, True])
def test_python_output_reference_validation_does_not_log_per_action(
    caplog: pytest.LogCaptureFixture, declared: bool
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.spec.python")
    references = [ref.output("temperature")]
    if declared:
        validation.validate_action_output_references("read", references, ["temperature"])
    else:
        with pytest.raises(ValueError, match="undeclared output 'temperature'"):
            validation.validate_action_output_references("read", references, [])

    assert not caplog.messages


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


def test_dataset_name_defaults_to_humanized_id() -> None:
    declaration = authoring.Profile(id="pump_telemetry-dataset")

    assert declaration.name == "Pump Telemetry Dataset"
    assert declaration.to_model().name == "Pump Telemetry Dataset"


def test_named_output_list_preserves_order_and_canonical_json_ids() -> None:
    declaration = authoring.Profile(
        id="example",
        actions=[
            authoring.Action(
                id="read",
                function=ref.function("reader:read", kind="read"),
                arguments={},
                outputs=[
                    authoring.Feature(
                        id="temperature",
                        name="Ambient Temperature",
                        type="float",
                        unit="C",
                        description="Ambient temperature measurement.",
                    ),
                    authoring.Feature(id="pump", type="string"),
                ],
            )
        ],
    )

    canonical = declaration.to_model()
    assert list(canonical.features) == ["temperature", "pump"]
    assert canonical.features["temperature"].id == "temperature"
    assert canonical.features["temperature"].name == "Ambient Temperature"
    assert canonical.features["pump"].name == "Pump"
    assert canonical.actions["read"].output_features == ["temperature", "pump"]
    payload = conversion.to_dict(profiles=[declaration])
    exported = payload["profiles"]["example"]
    assert exported["features"]["temperature"] == {
        "name": "Ambient Temperature",
        "type": "float",
        "unit": "C",
        "description": "Ambient temperature measurement.",
    }
    assert exported["actions"]["read"]["features"]["outputs"] == [
        "$features.temperature",
        "$features.pump",
    ]


def test_mapping_rejects_duplicate_output_ids() -> None:
    with pytest.raises(ValueError, match="output feature IDs must not repeat"):
        authoring.Action(
            id="action",
            function=ref.function("reader:read", kind="read"),
            arguments={},
            outputs=[
                authoring.Feature(id="temperature"),
                authoring.Feature(id="temperature"),
            ],
        )


def test_assembly_collects_inputs_without_executing_implementation() -> None:
    class Example(authoring.Profile):
        id = "example"
        actions = [
            authoring.Action(
                id="result",
                function=must_not_execute,
                arguments={
                    "values": [ref.feature("temperature"), ref.feature("temperature")],
                    "output": ref.feature("result").id,
                },
                outputs=[authoring.Feature(id="result", type="float")],
            )
        ]

    declaration = Example()
    action = declaration.actions[0]
    model = declaration.to_model().actions["result"]

    assert model.id == "result"
    assert model.input_features == ["temperature"]
    assert action.arguments == {
        "values": [ref.feature("temperature"), ref.feature("temperature")],
        "output": ref.feature("result").id,
    }
    assert action.bound_arguments() == action.arguments
    assert model.binding.args["output"] == "$features.result.id"
    assert action.outputs[0].id == "result"
    assert action.outputs[0].name == "Result"
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

    class Example(authoring.Profile):
        id = "example"
        actions = [
            authoring.Action(
                id="invalid",
                function=implementation,
                arguments=arguments,
                outputs=[],
            )
        ]

    with pytest.raises(TypeError, match="Profile 'example', action 'invalid'") as error:
        Example().to_model()
    assert message in str(error.value)


@pytest.mark.parametrize("identifier", ["result", "machine"])
def test_duplicate_producers_are_rejected(identifier: str) -> None:
    class Example(authoring.Profile):
        id = "example"
        actions = [
            authoring.Action(
                id="first",
                function=ref.function(
                    "test_declarative_authoring:implementation", kind="vectorize"
                ),
                arguments={"output": ref.feature(identifier).id},
                outputs=[authoring.Feature(id=identifier, type="float")],
            )
        ]
        actions = [*actions, dataclasses.replace(actions[0], id="second")]

    with pytest.raises(ValueError, match="'first' and 'second'"):
        Example().to_model()


def test_dataset_subclasses_inherit_and_replace_collections() -> None:
    first = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[authoring.Feature(id="value", type="float")],
    )
    replacement = authoring.Action(
        id="read",
        function=ref.function("reader:replacement", kind="read"),
        arguments={},
        outputs=[authoring.Feature(id="value", type="integer")],
    )
    sink = authoring.Action(
        id="write",
        function=ref.function("writer:write", kind="write"),
        arguments={"column": ref.feature("value")},
        outputs=[],
    )

    class Base(authoring.Profile):
        id = "base"
        description = "Inherited metadata"
        actions = [first, sink]

    class Derived(Base):
        id = "derived"
        actions = [replacement]

    base = Base()
    derived = Derived()
    assert base.actions == [first, sink]
    assert derived.actions == [replacement]
    assert list(derived.to_model().actions) == ["read"]
    assert derived.to_model().description == "Inherited metadata"
    assert derived.to_model().features["value"].type == "integer"
    assert set(derived.function_catalog()) == {"replacement"}


def test_dataset_requires_identifier() -> None:
    with pytest.raises((TypeError, ValueError), match="id"):
        authoring.Profile().to_model()


def test_profile_grain_supplies_dimension_resolution_metadata() -> None:
    identifier = dimension.Dimension(
        id="machine",
        description="Machine key",
        resolutions=[dimension.Resolution(id="machine", key="machine_id", type="string")],
    )

    class Example(authoring.Profile):
        id = "example"
        grain = [authoring.Grain(identifier, "machine")]
        actions = [
            authoring.Action(
                id="values",
                function=ref.function("reader:values", kind="read"),
                arguments={},
                outputs=[authoring.Feature(id="value", type="float")],
            )
        ]

    model = Example().to_model()

    assert model.features["machine_id"].type == "string"
    assert model.features["machine_id"].description == "Machine key"
    assert model.actions["values"].output_features == ["machine_id", "value"]


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
                "key": ref.current_profile().grain.ids,
            }
        },
        outputs=[authoring.Feature(id="result", type="float")],
    )
    model = action.to_model()
    assert action.inputs is None
    assert model.input_features == ["first", "second"]
    assert model.row_context.before.rows == 2
    assert model.binding.args["configuration"] == {
        "columns": ["$features.first", "$features.second", "$features.first"],
        "output": "$features.result.id",
        "key": "$profiles.@.grain.ids",
    }


def test_programmatic_dataset_preserves_mapping_names_and_function_overrides() -> None:
    action = authoring.Action(
        id="named",
        function=ref.function("calculation:calculate", kind="vectorize"),
        function_id="custom",
        arguments={"column": ref.feature("inferred")},
        inputs=[ref.feature("explicit")],
        outputs=[authoring.Feature(id="result", type="float")],
    )
    declaration = authoring.Profile(id="example", actions=[action])

    assert declaration.actions == [action]
    assert action.reference.entrypoint == "calculation:calculate"
    assert action.catalog_id == "custom"
    assert declaration.to_model().actions["named"].input_features == ["explicit"]
    assert declaration.to_model().actions["named"].binding.function == "custom"
    assert set(declaration.function_catalog()) == {"custom"}


def test_profile_grain_selector_is_preserved_and_typed_in_python_specs() -> None:
    identifier = dimension.Dimension(
        id="machine",
        resolutions=[dimension.Resolution(id="machine", key="machine_id", type="string")],
    )
    declaration = authoring.Profile(
        id="example",
        grain=[authoring.Grain(identifier, "machine")],
        actions=[
            authoring.Action(
                id="read",
                function=ref.function("reader:read", kind="read"),
                arguments={
                    "keys": ref.current_profile().grain.ids,
                    "source_keys": ref.profile("source").grain.ids,
                },
                outputs=[authoring.Feature(id="value", type="float")],
            )
        ],
    )

    model = declaration.to_model()
    catalog = declaration.function_catalog()
    assert model.actions["read"].binding.args["keys"] == "$profiles.@.grain.ids"
    assert model.actions["read"].binding.args["source_keys"] == "$profiles.source.grain.ids"
    assert catalog["read"].args["keys"].type == "array[string]"
    assert catalog["read"].args["source_keys"].type == "array[string]"

    payload = conversion.to_dict(profiles=[declaration])
    assert (
        payload["profiles"]["example"]["actions"]["read"]["binding"]["args"]["keys"]
        == "$profiles.@.grain.ids"
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
def test_actions_accept_every_declared_function_kind(kind: functions.FunctionKindId) -> None:
    action = authoring.Action(
        id="work",
        function=ref.function("implementation:work", kind=kind),
        arguments={},
        outputs=[],
    )
    declaration = authoring.Profile(id="example", actions=[action])
    assert declaration.to_model().actions["work"] == action.to_model()
    assert declaration.function_catalog()["work"].kind == kind


@pytest.mark.parametrize("invalid", ["invalid", [object()], [None]])
def test_action_list_rejects_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(
        TypeError, match="actions must (be a sequence or mapping of|contain) Actions"
    ):
        authoring.Profile(id="example", actions=invalid)


@pytest.mark.parametrize("invalid", [{}, "invalid", [object()], [None]])
def test_action_groups_reject_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(TypeError, match="action group 'calculations'"):
        authoring.Profile(id="example", actions={"calculations": invalid})


def test_action_groups_flatten_in_mapping_order() -> None:
    first = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )
    second = dataclasses.replace(
        first,
        id="write",
        function=ref.function("writer:write", kind="write"),
    )
    declaration = authoring.Profile(
        id="example",
        actions={"ingestion": [first], "publishing": [second]},
    )

    assert declaration.actions == [first, second]
    assert list(declaration.to_model().actions) == ["read", "write"]
    assert authoring.Profile(id="empty_grouped", actions={}).actions == []


@pytest.mark.parametrize("second_kind", ["read", "write", "escape"])
def test_action_ids_are_unique_across_groups(second_kind: functions.FunctionKindId) -> None:
    first = authoring.Action(
        id="duplicate",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )
    second = dataclasses.replace(
        first, function=ref.function("implementation:work", kind=second_kind)
    )
    with pytest.raises(ValueError, match="Profile 'example' has duplicate action ID 'duplicate'"):
        authoring.Profile(
            id="example",
            actions={"first": [first], "second": [second]},
        )


def test_action_defaults_and_inherited_lists_are_not_shared_between_instances() -> None:
    read = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )

    class Base(authoring.Profile):
        id = "base"
        actions = [read]

    first = Base()
    second = Base()
    assert isinstance(first.actions, list)
    first.actions.clear()
    assert second.actions == Base.actions == [read]
    assert Base(actions=[]).actions == []

    supplied = [read]
    constructed = authoring.Profile(id="constructed", actions=supplied)
    supplied.clear()
    assert constructed.actions == [read]


def test_subclasses_can_explicitly_extend_or_clear_inherited_actions() -> None:
    read = authoring.Action(
        id="read",
        function=ref.function("reader:read", kind="read"),
        arguments={},
        outputs=[],
    )

    class Base(authoring.Profile):
        id = "base"
        actions = [read]

    class Extended(Base):
        actions = [*Base.actions, dataclasses.replace(read, id="another_read")]

    class Empty(Base):
        actions = []

    assert list(Extended().to_model().actions) == ["read", "another_read"]
    assert Empty().to_model().actions == {}
    assert Base.actions == [read]


def test_conversion_revalidates_modified_actions() -> None:
    declaration = authoring.Profile(id="example")
    declaration.actions = [
        authoring.Action(
            id="write",
            function=ref.function("writer:write", kind="write"),
            arguments={},
            outputs=[],
        )
    ]
    declaration.actions[0] = dataclasses.replace(
        declaration.actions[0], outputs=[authoring.Feature(id="value")]
    )
    with pytest.raises(ValueError, match="Write action cannot produce features"):
        declaration.to_model()
    with pytest.raises(ValueError, match="Write action cannot produce features"):
        declaration.function_catalog()


def test_grouped_actions_preserve_dependencies_and_canonical_mapping_ids() -> None:
    class Example(authoring.Profile):
        id = "example"
        actions = {
            "calculations": [
                authoring.Action(
                    id="calculate",
                    function=ref.function("implementation:calculate", kind="vectorize"),
                    arguments={"column": ref.feature("pipeline_result")},
                    outputs=[authoring.Feature(id="result")],
                )
            ],
            "publishing": [
                authoring.Action(
                    id="publish",
                    function=ref.function("implementation:publish", kind="write"),
                    arguments={"column": ref.feature("result")},
                    outputs=[],
                )
            ],
            "custom": [
                authoring.Action(
                    id="custom_work",
                    function=ref.function("implementation:custom_work", kind="escape"),
                    arguments={},
                    inputs=[ref.feature("external_input")],
                    outputs=[],
                )
            ],
        }

    declaration = Example()
    assert [action.id for action in declaration.actions] == [
        "calculate",
        "publish",
        "custom_work",
    ]
    model = declaration.to_model()
    assert list(model.actions) == ["calculate", "publish", "custom_work"]
    assert model.actions["calculate"].input_features == ["pipeline_result"]
    assert model.actions["publish"].input_features == ["result"]
    assert model.actions["custom_work"].input_features == ["external_input"]
    payload = conversion.to_dict(profiles=[declaration])
    exported = payload["profiles"]["example"]
    assert set(exported["actions"]) == {"calculate", "publish", "custom_work"}
    assert set(exported["features"]) == {"result"}


def test_dataset_registry_collects_dataset_classes_in_order() -> None:
    class First(authoring.Profile):
        id = "first"

    class Second(authoring.Profile):
        id = "second"

    declarations = authoring.ProfileRegistry(profiles=[First, Second]).to_declarations()
    assert list(declarations) == ["first", "second"]
    assert isinstance(declarations["first"], First)
    assert isinstance(declarations["second"], Second)
