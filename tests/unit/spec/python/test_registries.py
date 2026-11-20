import dataclasses
import typing

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, merge, ref
from uptimely.spec.validation import errors as validation_errors
from uptimely.spec.validation import validate_spec


@authoring.function(returns="dataframe")
def merge_frames(dataset: object | None, fragment: object) -> object:
    """Return the merged dataframe."""
    return dataset if dataset is not None else fragment


@authoring.function(returns="dataframe")
def read_frames() -> object:
    """Return source observations."""
    return object()


def test_python_spec_merge_binding_export() -> None:
    operator = authoring.Operator(
        id="read",
        outputs=[authoring.Feature(id="value")],
        compute=authoring.Bind(
            read_frames,
        ),
        merge=authoring.Bind(
            merge_frames,
            dataset=ref.dataset(),
            fragment=ref.fragment(),
        ),
    )
    declaration = authoring.Profile(id="example", assembly=[operator])
    spec_definition = authoring.Spec(profiles=[declaration]).to_model()
    validate_spec(spec_definition)
    model_operator = spec_definition.profiles["example"].assembly["read"]

    assert spec_definition.spec_version == 9
    assert model_operator.merge is not None
    assert model_operator.merge.model_dump()["args"] == {
        "dataset": "$profiles.@.dataset",
        "fragment": "$operators.@.fragment",
    }
    assert spec_definition.functions["merge_frames"].args["dataset"].type == "dataframe | null"
    assert spec_definition.functions["merge_frames"].args["fragment"].type == "dataframe"
    assert "options" not in spec_definition.model_dump()
    assert "options" not in authoring.Spec(profiles=[declaration]).to_dict()
    validate_spec(spec_model.Spec.model_validate(spec_definition.model_dump()))

    invalid_spec = spec_model.Spec.model_validate(spec_definition.model_dump())
    merge_template = invalid_spec.functions["merge_frames"]
    merge_template.args["feature"] = spec_model.Argument(id="feature", type="string")
    invalid_spec.profiles["example"].assembly["read"].merge.args["feature"] = (
        spec_model.BindingArgument("$features.value")
    )
    with pytest.raises(validation_errors.SpecError, match="cannot reference features") as error:
        validate_spec(invalid_spec)
    assert error.value.code == "invalid_merge_feature_reference"


@pytest.mark.parametrize("invalid", ["invalid", [object()], [None]])
def test_operator_list_rejects_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(
        TypeError, match="assembly must (be a sequence or mapping of|contain) Operators"
    ):
        authoring.Profile(id="example", assembly=invalid)


@pytest.mark.parametrize("invalid", [{}, "invalid", [object()], [None]])
def test_operator_groups_reject_invalid_values(invalid: typing.Any) -> None:
    with pytest.raises(TypeError, match="assembly group 'calculations'"):
        authoring.Profile(id="example", assembly={"calculations": invalid})


def test_operator_groups_flatten_in_mapping_order() -> None:
    first = authoring.Operator(
        id="read",
        outputs=[],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
        merge=merge.default(),
    )
    second = authoring.Operator(
        id="write",
        outputs=[],
        compute=authoring.Bind(
            ref.function("writer:write", returns="none"),
            dataset=ref.dataset(),
        ),
    )
    declaration = authoring.Profile(
        id="example",
        assembly={"ingestion": [first], "publishing": [second]},
    )

    assert declaration.assembly == [first, second]
    assert list(declaration.to_model().assembly) == ["read", "write"]
    assert authoring.Profile(id="empty_grouped", assembly={}).assembly == []


@pytest.mark.parametrize("returns", ["dataframe", "none", "any"])
def test_operator_ids_are_unique_across_groups(returns: str) -> None:
    first = authoring.Operator(
        id="duplicate",
        outputs=[],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
        merge=merge.default(),
    )
    second = authoring.Operator(
        id="duplicate",
        outputs=[],
        compute=authoring.Bind(ref.function("implementation:work", returns=returns)),
    )
    with pytest.raises(ValueError, match="Profile 'example' has duplicate operator ID 'duplicate'"):
        authoring.Profile(
            id="example",
            assembly={"first": [first], "second": [second]},
        )


def test_operator_defaults_and_inherited_lists_are_not_shared_between_instances() -> None:
    read = authoring.Operator(
        id="read",
        outputs=[],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
        merge=merge.default(),
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


def test_subclasses_can_explicitly_extend_or_clear_inherited_operator() -> None:
    read = authoring.Operator(
        id="read",
        outputs=[],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
        merge=merge.default(),
    )

    class Base(authoring.Profile):
        id = "base"
        assembly = [read]

    class Extended(Base):
        assembly = [*Base.assembly, dataclasses.replace(read, id="another_read")]

    class Empty(Base):
        assembly = []

    assert list(Extended().to_model().assembly) == ["read", "another_read"]
    assert Empty().to_model().assembly == {}
    assert Base.assembly == [read]


def test_conversion_revalidates_modified_operator() -> None:
    declaration = authoring.Profile(id="example")
    declaration.assembly = [
        authoring.Operator(
            id="write",
            outputs=[],
            compute=authoring.Bind(
                ref.function("writer:write", returns="none"),
                dataset=ref.dataset(),
            ),
        )
    ]
    declaration.assembly[0] = dataclasses.replace(
        declaration.assembly[0],
        outputs=[authoring.Feature(id="value")],
    )
    with pytest.raises(ValueError, match="No-result operator cannot produce features"):
        declaration.to_model()
    with pytest.raises(ValueError, match="No-result operator cannot produce features"):
        declaration.function_catalog()


def test_grouped_operator_preserve_dependencies_and_canonical_operator_ids() -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = {
            "calculations": [
                authoring.Operator(
                    id="calculate",
                    outputs=[authoring.Feature(id="result")],
                    compute=authoring.Bind(
                        ref.function("implementation:calculate", returns="dataframe"),
                        dataset=ref.dataset(),
                        column=ref.feature("pipeline_result"),
                    ),
                )
            ],
            "publishing": [
                authoring.Operator(
                    id="publish",
                    outputs=[],
                    compute=authoring.Bind(
                        ref.function("implementation:publish", returns="none"),
                        dataset=ref.dataset(),
                        column=ref.feature("result"),
                    ),
                )
            ],
            "custom": [
                authoring.Operator(
                    id="custom_work",
                    inputs=[ref.feature("external_input")],
                    outputs=[],
                    compute=authoring.Bind(
                        ref.function("implementation:custom_work", returns="any"),
                    ),
                )
            ],
        }

    declaration = Example()
    assert [operator.id for operator in declaration.assembly] == [
        "calculate",
        "publish",
        "custom_work",
    ]
    model = declaration.to_model()
    assert list(model.assembly) == ["calculate", "publish", "custom_work"]
    assert model.assembly["calculate"].input_features == ["pipeline_result"]
    assert model.assembly["publish"].input_features == ["result"]
    assert model.assembly["custom_work"].input_features == ["external_input"]
    payload = conversion.to_dict(profiles=[declaration])
    exported = payload["profiles"]["example"]
    assert set(exported["assembly"]) == {"calculate", "publish", "custom_work"}
    assert set(exported["features"]) == {"result"}


def test_profile_registry_collects_profile_classes_in_order() -> None:
    class First(authoring.Profile):
        id = "first"

    class Second(authoring.Profile):
        id = "second"

    declarations = authoring.ProfileRegistry(profiles=[First, Second]).to_declarations()
    assert list(declarations) == ["first", "second"]
    assert isinstance(declarations["first"], First)
    assert isinstance(declarations["second"], Second)
