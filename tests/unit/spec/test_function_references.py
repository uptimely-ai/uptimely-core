import dataclasses
import importlib
import json
import math
import typing
from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import operations
from uptimely.spec.python import bind, conversion, dataset, mapping, ref

MODULE_LOCATIONS = [
    "math",
    "functions/calculation.py",
    "./functions/calculation.py",
    "/opt/spec/calculation.py",
    "https://example.org/calculation.py",
    "https://example.org/team/repository.git",
    "git@example.org:team/repository.git",
]
MAPPING_OPERATIONS: tuple[operations.FunctionOperation, ...] = (
    "read",
    "write",
    "escape",
    "vectorize",
    "collapse",
    "expand",
    "conform",
)


@pytest.mark.parametrize("function", [math.ceil, "math:ceil"])
def test_callable_and_string_forms_have_identical_entrypoints(
    function: abc.Callable[..., object] | str,
) -> None:
    reference = ref.function(function)

    assert reference.module == "math"
    assert reference.name == "ceil"
    assert reference.entrypoint == "math:ceil"
    assert reference.validate_signature is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        reference.name = "floor"


def test_function_reference_rejects_unsupported_operation() -> None:
    with pytest.raises(ValueError, match="Unsupported function operation"):
        ref.function("math:ceil", operation=typing.cast(operations.FunctionOperation, "unknown"))


@pytest.mark.parametrize("operation", MAPPING_OPERATIONS)
@pytest.mark.parametrize("validate_signature", [False, True])
def test_signature_validation_setting_survives_conversion_without_importing(
    operation: operations.FunctionOperation,
    validate_signature: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail("Converting a function reference must not import its module")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    reference = ref.function(
        "unavailable_package.functions:calculate",
        operation=operation,
        validate_signature=validate_signature,
    )
    declaration = dataset.Dataset(
        id="observations",
        mappings={
            "calculate": mapping.FunctionMapping(function=reference, arguments={}, outputs=[])
        },
    )

    payload = conversion.to_dict(datasets=[declaration])
    reloaded = spec_model.Spec.model_validate(json.loads(json.dumps(payload)))

    assert reference.validate_signature is validate_signature
    assert payload["functions"]["calculate"]["validate_signature"] is validate_signature
    assert reloaded.functions["calculate"].validate_signature is validate_signature


@pytest.mark.parametrize("validate_signature", [None, "false", 0, 1])
def test_function_reference_rejects_non_boolean_signature_validation(
    validate_signature: typing.Any,
) -> None:
    with pytest.raises(TypeError, match="validate_signature must be a boolean"):
        ref.function("math:ceil", validate_signature=validate_signature)


def test_function_model_defaults_signature_validation_and_exposes_schema() -> None:
    function = spec_model.FunctionTemplate(
        id="calculate",
        operation="vectorize",
        returns="dataframe",
        entrypoint="unavailable_package:calculate",
    )

    assert function.validate_signature is True
    assert function.model_dump()["validate_signature"] is True
    schema = spec_model.FunctionTemplate.model_json_schema()
    assert schema["properties"]["validate_signature"]["type"] == "boolean"
    assert schema["properties"]["validate_signature"]["default"] is True


def test_conflicting_signature_validation_settings_are_rejected() -> None:
    declarations = [
        dataset.Dataset(
            id=identifier,
            mappings={
                "ceil": mapping.FunctionMapping(
                    inputs=[],
                    function=ref.function(
                        "math:ceil", operation="vectorize", validate_signature=validate_signature
                    ),
                    arguments={},
                    outputs=[],
                )
            },
        )
        for identifier, validate_signature in [("first", True), ("second", False)]
    ]

    with pytest.raises(ValueError, match="Conflicting function definition for 'ceil'"):
        conversion.to_dict(datasets=declarations)


@pytest.mark.parametrize("location", MODULE_LOCATIONS)
def test_string_locations_are_preserved_without_importing(
    location: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail("Creating or exporting a function reference must not import its module")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    reference = ref.function(f"{location}:ceil", operation="vectorize")
    declaration = dataset.Dataset(
        id="observations",
        mappings={
            "ceil": mapping.FunctionMapping(function=reference, arguments={"x": 1.2}, outputs=[])
        },
    )

    payload = conversion.to_dict(datasets=[declaration])

    assert payload["functions"]["ceil"]["entrypoint"] == f"{location}:ceil"
    assert payload["entities"]["entity"]["datasets"]["observations"]["mappings"]["ceil"][
        "binding"
    ] == {
        "function": "ceil",
        "args": {"x": 1.2},
    }


@pytest.mark.parametrize("operation", MAPPING_OPERATIONS)
def test_generic_mapping_exports_function_operation_without_importing(
    operation: operations.FunctionOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail(f"Unexpected function import during authoring: {_args!r} {_kwargs!r}")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    declaration = dataset.Dataset(
        id="observations",
        mappings={
            "calculate": mapping.FunctionMapping(
                inputs=[],
                function=ref.function(
                    "https://example.org/functions.py:calculate", operation=operation
                ),
                arguments={"dataset": ref.current_dataset().dataframe},
                outputs=[],
                function_id="calculate",
            )
        },
    )

    catalog = declaration.function_catalog()

    assert catalog["calculate"].operation == operation
    expected_returns = {
        "write": "none",
        "escape": "any",
    }.get(operation, "dataframe")
    assert catalog["calculate"].returns == expected_returns
    assert catalog["calculate"].entrypoint == "https://example.org/functions.py:calculate"


def test_generic_mapping_requires_operation_metadata() -> None:
    with pytest.raises(ValueError, match="operation"):
        mapping.FunctionMapping(
            inputs=[],
            function=ref.function("math:ceil"),
            arguments={"x": 1.2},
            outputs=[],
        )


def test_escape_catalog_metadata_survives_json_round_trip() -> None:
    declaration = dataset.Dataset(
        id="observations",
        mappings={
            "external_update": mapping.FunctionMapping(
                inputs=[],
                function=ref.function("math:ceil", operation="escape"),
                arguments={},
                outputs=[],
            )
        },
    )

    payload = conversion.to_dict(datasets=[declaration])
    reloaded = spec_model.Spec.model_validate(json.loads(json.dumps(payload)))

    assert payload["functions"]["ceil"]["operation"] == "escape"
    assert payload["functions"]["ceil"]["returns"] == "any"
    assert reloaded.functions["ceil"].operation == "escape"
    assert reloaded.functions["ceil"].returns == "any"


@pytest.mark.parametrize("operation", MAPPING_OPERATIONS)
def test_generic_mapping_accepts_operation_metadata(
    operation: operations.FunctionOperation,
) -> None:
    declaration = mapping.FunctionMapping(
        inputs=[],
        function=ref.function("math:ceil", operation=operation),
        arguments={"x": 1.2},
        outputs=[],
    )

    assert declaration.operation == operation


@pytest.mark.parametrize("operation", MAPPING_OPERATIONS)
@pytest.mark.parametrize("function_id", [None, "rounded"])
def test_references_supply_catalog_ids_and_preserve_overrides(
    operation: operations.FunctionOperation, function_id: str | None
) -> None:
    declaration = mapping.FunctionMapping(
        function=ref.function("math:ceil", operation=operation),
        function_id=function_id,
        arguments={"x": 1.2},
        outputs=[],
    )
    catalog = dataset.Dataset(id="values", mappings={"calculate": declaration}).function_catalog()
    identifier = function_id or "ceil"

    assert catalog[identifier].operation == operation
    assert catalog[identifier].entrypoint == "math:ceil"
    assert catalog[identifier].args["x"].type == "float"
    model = declaration.to_model("calculate")
    assert model.id == "calculate"
    assert model.binding.function == identifier
    assert model.binding.args == {"x": 1.2}


def test_nested_bindings_use_reference_names_and_overrides() -> None:
    binding = bind.bind(
        ref.function("math:ceil"),
        x=bind.bind(ref.function(math.floor), function_id="rounded", x=1.2),
    )

    assert bind._binding_args(binding) == {"x": {"function": "rounded", "args": {"x": 1.2}}}


@pytest.mark.parametrize("entrypoint", ["", "ceil", "math.ceil", "path/to/module.py"])
def test_entrypoints_require_a_module_and_function_separator(entrypoint: str) -> None:
    with pytest.raises(ValueError, match="module:function"):
        ref.function(entrypoint)


@pytest.mark.parametrize("module", ["", "  "])
def test_empty_module_locations_are_rejected(module: str) -> None:
    with pytest.raises(ValueError, match="module must not be empty"):
        ref.function(f"{module}:ceil")


@pytest.mark.parametrize("function", [None, 42, object(), math])
def test_invalid_function_types_are_rejected(function: typing.Any) -> None:
    with pytest.raises(TypeError, match="callable or a string"):
        ref.function(function)


@pytest.mark.parametrize("name", ["", "  ", "ceil()", "a.b", "<lambda>"])
def test_invalid_function_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="Python identifier"):
        ref.function(f"math:{name}")


def test_callable_without_a_name_requires_a_string() -> None:
    class Callable:
        def __call__(self) -> None:
            pass

    with pytest.raises(ValueError, match="pass an entrypoint string"):
        ref.function(Callable())


def test_callable_without_a_module_requires_an_entrypoint_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def calculate() -> None:
        pass

    monkeypatch.setattr(calculate, "__module__", None)
    with pytest.raises(ValueError, match="module and function name"):
        ref.function(calculate)


def test_lambda_is_rejected_as_an_unnamed_function() -> None:
    with pytest.raises(ValueError, match="Python identifier"):
        ref.function(lambda: None)


@pytest.mark.parametrize("factory", [bind.bind, bind.Bind])
@pytest.mark.parametrize("function", [math.ceil, "ceil", None])
def test_bind_requires_a_function_reference(factory: typing.Any, function: typing.Any) -> None:
    with pytest.raises(TypeError, match=r"ref.function\(callable_or_entrypoint\)"):
        factory(function, args={}) if factory is bind.Bind else factory(function)
