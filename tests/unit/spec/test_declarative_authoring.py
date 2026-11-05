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


def test_operator_is_the_public_work_declaration_name() -> None:
    assert authoring.Operator.__name__ == "Operator"
    assert not hasattr(authoring, "Action")
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
        assembly=[
            authoring.Operator(
                id="read",
                interface=authoring.Interface(
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
                ),
                compute=authoring.Binding(
                    function=ref.function("reader:read", kind="read"),
                    arguments={},
                ),
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
        authoring.Operator(
            id="action",
            interface=authoring.Interface(
                outputs=[
                    authoring.Feature(id="temperature"),
                    authoring.Feature(id="temperature"),
                ],
            ),
            compute=authoring.Binding(
                function=ref.function("reader:read", kind="read"),
                arguments={},
            ),
        )


def test_assembly_collects_inputs_without_executing_implementation() -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = [
            authoring.Operator(
                id="result",
                interface=authoring.Interface(
                    outputs=[authoring.Feature(id="result", type="float")],
                ),
                compute=authoring.Binding(
                    function=must_not_execute,
                    arguments={
                        "values": [ref.feature("temperature"), ref.feature("temperature")],
                        "output": ref.feature("result").id,
                    },
                ),
            )
        ]

    declaration = Example()
    action = declaration.assembly[0]
    model = declaration.to_model().actions["result"]

    assert model.id == "result"
    assert model.input_features == ["temperature"]
    assert action.compute.arguments == {
        "values": [ref.feature("temperature"), ref.feature("temperature")],
        "output": ref.feature("result").id,
    }
    assert action.bound_arguments() == action.compute.arguments
    assert model.binding.args["output"] == "$features.result.id"
    assert action.interface.outputs[0].id == "result"
    assert action.interface.outputs[0].name == "Result"
    assert action.interface.outputs[0].type == "float"


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
        assembly = [
            authoring.Operator(
                id="invalid",
                interface=authoring.Interface(
                    outputs=[],
                ),
                compute=authoring.Binding(
                    function=implementation,
                    arguments=arguments,
                ),
            )
        ]

    with pytest.raises(TypeError, match="Profile 'example', operator 'invalid'") as error:
        Example().to_model()
    assert message in str(error.value)


@pytest.mark.parametrize("identifier", ["result", "machine"])
def test_duplicate_producers_are_rejected(identifier: str) -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = [
            authoring.Operator(
                id="first",
                interface=authoring.Interface(
                    outputs=[authoring.Feature(id=identifier, type="float")],
                ),
                compute=authoring.Binding(
                    function=ref.function(
                        "test_declarative_authoring:implementation", kind="vectorize"
                    ),
                    arguments={"output": ref.feature(identifier).id},
                ),
            )
        ]
        assembly = [*assembly, dataclasses.replace(assembly[0], id="second")]

    with pytest.raises(ValueError, match="'first' and 'second'"):
        Example().to_model()


def test_dataset_subclasses_inherit_and_replace_collections() -> None:
    first = authoring.Operator(
        id="read",
        interface=authoring.Interface(
            outputs=[authoring.Feature(id="value", type="float")],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )
    replacement = authoring.Operator(
        id="read",
        interface=authoring.Interface(
            outputs=[authoring.Feature(id="value", type="integer")],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:replacement", kind="read"),
            arguments={},
        ),
    )
    sink = authoring.Operator(
        id="write",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("writer:write", kind="write"),
            arguments={"column": ref.feature("value")},
        ),
    )

    class Base(authoring.Profile):
        id = "base"
        description = "Inherited metadata"
        assembly = [first, sink]

    class Derived(Base):
        id = "derived"
        assembly = [replacement]

    base = Base()
    derived = Derived()
    assert base.assembly == [first, sink]
    assert derived.assembly == [replacement]
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
        assembly = [
            authoring.Operator(
                id="values",
                interface=authoring.Interface(
                    outputs=[authoring.Feature(id="value", type="float")],
                ),
                compute=authoring.Binding(
                    function=ref.function("reader:values", kind="read"),
                    arguments={},
                ),
            )
        ]

    model = Example().to_model()

    assert model.features["machine_id"].type == "string"
    assert model.features["machine_id"].description == "Machine key"
    assert model.actions["values"].output_features == ["machine_id", "value"]


def test_nested_arguments_infer_inputs_without_identifier_selectors() -> None:
    action = authoring.Operator(
        id="result",
        interface=authoring.Interface(
            outputs=[authoring.Feature(id="result", type="float")],
        ),
        compute=authoring.Binding(
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
        ),
    )
    model = action.to_model()
    assert action.interface.inputs is None
    assert model.input_features == ["first", "second"]
    assert model.row_context.before.rows == 2
    assert model.binding.args["configuration"] == {
        "columns": ["$features.first", "$features.second", "$features.first"],
        "output": "$features.result.id",
        "key": "$profiles.@.grain.ids",
    }


def test_programmatic_dataset_uses_function_name_for_catalog_id() -> None:
    action = authoring.Operator(
        id="named",
        interface=authoring.Interface(
            inputs=[ref.feature("explicit")],
            outputs=[authoring.Feature(id="result", type="float")],
        ),
        compute=authoring.Binding(
            function=ref.function("calculation:calculate", kind="vectorize"),
            arguments={"column": ref.feature("inferred")},
        ),
    )
    declaration = authoring.Profile(id="example", assembly=[action])

    assert declaration.assembly == [action]
    assert action.reference.entrypoint == "calculation:calculate"
    assert action.catalog_id == "calculate"
    assert declaration.to_model().actions["named"].input_features == ["explicit"]
    assert declaration.to_model().actions["named"].binding.function == "calculate"
    assert set(declaration.function_catalog()) == {"calculate"}


def test_action_interface_inputs_accept_feature_declarations() -> None:
    action = authoring.Operator(
        id="calculate",
        interface=authoring.Interface(
            inputs=[authoring.Feature(id="explicit")],
            outputs=[authoring.Feature(id="result")],
        ),
        compute=authoring.Binding(
            function=ref.function("calculation:calculate", kind="vectorize"),
            arguments={"value": ref.feature("inferred")},
        ),
    )

    assert action.to_model().input_features == ["explicit"]
    assert action.to_model().output_features == ["result"]


def test_profile_grain_selector_is_preserved_and_typed_in_python_specs() -> None:
    identifier = dimension.Dimension(
        id="machine",
        resolutions=[dimension.Resolution(id="machine", key="machine_id", type="string")],
    )
    declaration = authoring.Profile(
        id="example",
        grain=[authoring.Grain(identifier, "machine")],
        assembly=[
            authoring.Operator(
                id="read",
                interface=authoring.Interface(
                    outputs=[authoring.Feature(id="value", type="float")],
                ),
                compute=authoring.Binding(
                    function=ref.function("reader:read", kind="read"),
                    arguments={
                        "keys": ref.current_profile().grain.ids,
                        "source_keys": ref.profile("source").grain.ids,
                    },
                ),
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


@pytest.mark.parametrize("required", ["id", "interface", "compute"])
def test_mapping_constructor_requires_explicit_fields(required: str) -> None:
    arguments = {
        "id": "read",
        "interface": authoring.Interface(outputs=[]),
        "compute": authoring.Binding(function=ref.function("reader:read", kind="read")),
    }
    del arguments[required]
    with pytest.raises(TypeError, match=required):
        authoring.Operator(**arguments)


@pytest.mark.parametrize("legacy", ["function", "arguments", "outputs", "inputs", "function_id"])
def test_operator_rejects_flat_declaration_fields(legacy: str) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        authoring.Operator(
            id="read",
            interface=authoring.Interface(outputs=[]),
            compute=authoring.Binding(function=ref.function("reader:read", kind="read")),
            **{legacy: None},
        )


def test_mapping_requires_function_kind_metadata() -> None:
    with pytest.raises(ValueError, match="Function kind is required"):
        authoring.Operator(
            id="action",
            interface=authoring.Interface(
                outputs=[],
            ),
            compute=authoring.Binding(
                function="reader:read",
                arguments={},
            ),
        )


def test_kind_annotation_is_inferred_without_wrapping_function() -> None:
    declaration = authoring.Operator(
        id="declaration",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=calculate,
            arguments={"value": "input"},
        ),
    )

    assert declaration.compute.function is calculate
    assert declaration.kind == "vectorize"
    assert declaration.function_catalog()["calculate"].kind == "vectorize"


def test_action_export_uses_its_identifier() -> None:
    action = authoring.Operator(
        id="action",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )
    assert action.to_model().id == "action"


@pytest.mark.parametrize("identifier", ["", " ", None, 1])
def test_action_rejects_invalid_identifiers(identifier: typing.Any) -> None:
    with pytest.raises(ValueError, match="Operator requires a non-empty id"):
        authoring.Operator(
            id=identifier,
            interface=authoring.Interface(
                outputs=[],
            ),
            compute=authoring.Binding(
                function=ref.function("reader:read", kind="read"),
                arguments={},
            ),
        )


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
def test_actions_accept_every_declared_function_kind(kind: functions.FunctionKindId) -> None:
    action = authoring.Operator(
        id="work",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("implementation:work", kind=kind),
            arguments={},
        ),
    )
    declaration = authoring.Profile(id="example", assembly=[action])
    assert declaration.to_model().actions["work"] == action.to_model()
    assert declaration.function_catalog()["work"].kind == kind


@pytest.mark.parametrize("invalid", ["invalid", [object()], [None]])
def test_action_list_rejects_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(
        TypeError, match="assembly must (be a sequence or mapping of|contain) Operators"
    ):
        authoring.Profile(id="example", assembly=invalid)


@pytest.mark.parametrize("invalid", [{}, "invalid", [object()], [None]])
def test_action_groups_reject_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(TypeError, match="assembly group 'calculations'"):
        authoring.Profile(id="example", assembly={"calculations": invalid})


def test_action_groups_flatten_in_mapping_order() -> None:
    first = authoring.Operator(
        id="read",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )
    second = dataclasses.replace(
        first,
        id="write",
        compute=dataclasses.replace(
            first.compute,
            function=ref.function("writer:write", kind="write"),
        ),
    )
    declaration = authoring.Profile(
        id="example",
        assembly={"ingestion": [first], "publishing": [second]},
    )

    assert declaration.assembly == [first, second]
    assert list(declaration.to_model().actions) == ["read", "write"]
    assert authoring.Profile(id="empty_grouped", assembly={}).assembly == []


@pytest.mark.parametrize("second_kind", ["read", "write", "escape"])
def test_action_ids_are_unique_across_groups(second_kind: functions.FunctionKindId) -> None:
    first = authoring.Operator(
        id="duplicate",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )
    second = dataclasses.replace(
        first,
        compute=dataclasses.replace(
            first.compute,
            function=ref.function("implementation:work", kind=second_kind),
        ),
    )
    with pytest.raises(ValueError, match="Profile 'example' has duplicate operator ID 'duplicate'"):
        authoring.Profile(
            id="example",
            assembly={"first": [first], "second": [second]},
        )


def test_action_defaults_and_inherited_lists_are_not_shared_between_instances() -> None:
    read = authoring.Operator(
        id="read",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )

    class Base(authoring.Profile):
        id = "base"
        assembly = [read]

    first = Base()
    second = Base()
    assert isinstance(first.assembly, list)
    first.assembly.clear()
    assert second.assembly == Base.assembly == [read]
    assert Base(assembly=[]).assembly == []

    supplied = [read]
    constructed = authoring.Profile(id="constructed", assembly=supplied)
    supplied.clear()
    assert constructed.assembly == [read]


def test_subclasses_can_explicitly_extend_or_clear_inherited_actions() -> None:
    read = authoring.Operator(
        id="read",
        interface=authoring.Interface(
            outputs=[],
        ),
        compute=authoring.Binding(
            function=ref.function("reader:read", kind="read"),
            arguments={},
        ),
    )

    class Base(authoring.Profile):
        id = "base"
        assembly = [read]

    class Extended(Base):
        assembly = [*Base.assembly, dataclasses.replace(read, id="another_read")]

    class Empty(Base):
        assembly = []

    assert list(Extended().to_model().actions) == ["read", "another_read"]
    assert Empty().to_model().actions == {}
    assert Base.assembly == [read]


def test_conversion_revalidates_modified_actions() -> None:
    declaration = authoring.Profile(id="example")
    declaration.assembly = [
        authoring.Operator(
            id="write",
            interface=authoring.Interface(
                outputs=[],
            ),
            compute=authoring.Binding(
                function=ref.function("writer:write", kind="write"),
                arguments={},
            ),
        )
    ]
    declaration.assembly[0] = dataclasses.replace(
        declaration.assembly[0],
        interface=dataclasses.replace(
            declaration.assembly[0].interface,
            outputs=[authoring.Feature(id="value")],
        ),
    )
    with pytest.raises(ValueError, match="Write operator cannot produce features"):
        declaration.to_model()
    with pytest.raises(ValueError, match="Write operator cannot produce features"):
        declaration.function_catalog()


def test_grouped_actions_preserve_dependencies_and_canonical_mapping_ids() -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = {
            "calculations": [
                authoring.Operator(
                    id="calculate",
                    interface=authoring.Interface(
                        outputs=[authoring.Feature(id="result")],
                    ),
                    compute=authoring.Binding(
                        function=ref.function("implementation:calculate", kind="vectorize"),
                        arguments={"column": ref.feature("pipeline_result")},
                    ),
                )
            ],
            "publishing": [
                authoring.Operator(
                    id="publish",
                    interface=authoring.Interface(
                        outputs=[],
                    ),
                    compute=authoring.Binding(
                        function=ref.function("implementation:publish", kind="write"),
                        arguments={"column": ref.feature("result")},
                    ),
                )
            ],
            "custom": [
                authoring.Operator(
                    id="custom_work",
                    interface=authoring.Interface(
                        inputs=[ref.feature("external_input")],
                        outputs=[],
                    ),
                    compute=authoring.Binding(
                        function=ref.function("implementation:custom_work", kind="escape"),
                        arguments={},
                    ),
                )
            ],
        }

    declaration = Example()
    assert [action.id for action in declaration.assembly] == [
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
