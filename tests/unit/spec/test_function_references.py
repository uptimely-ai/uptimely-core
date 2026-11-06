import dataclasses
import importlib
import json
import math
import typing
from collections import abc

import pytest

from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, bind, binding_conversion, conversion, profile, ref

MODULE_LOCATIONS = [
    "math",
    "unavailable_package.functions",
]
MAPPING_KINDS: tuple[functions.FunctionKindId, ...] = (
    "read",
    "write",
    "escape",
    "vectorize",
    "collapse",
    "expand",
    "conform",
)


def _dataset(operator: assembly.Operator) -> profile.Profile:
    return profile.Profile(
        id="observations",
        assembly=[operator],
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


def test_function_reference_accepts_qualified_names() -> None:
    reference = ref.function("decimal:Decimal.from_float")

    assert reference.name == "Decimal.from_float"
    assert reference.entrypoint == "decimal:Decimal.from_float"


def test_function_reference_rejects_unsupported_operation() -> None:
    with pytest.raises(ValueError, match="Unsupported function kind"):
        ref.function("math:ceil", kind=typing.cast(functions.FunctionKindId, "unknown"))


@pytest.mark.parametrize("kind", MAPPING_KINDS)
@pytest.mark.parametrize("validate_signature", [False, True])
def test_signature_validation_setting_survives_conversion_without_importing(
    kind: functions.FunctionKindId,
    validate_signature: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail("Converting a function reference must not import its module")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    reference = ref.function(
        "unavailable_package.functions:calculate",
        kind=kind,
        validate_signature=validate_signature,
    )
    declaration = _dataset(
        assembly.Operator(
            id="calculate",
            interface=assembly.Interface(
                outputs=[],
            ),
            compute=assembly.Binding(
                function=reference,
                arguments={},
            ),
        ),
    )

    payload = conversion.to_dict(profiles=[declaration])
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


def _documented(dataset: object) -> object:
    """Summary line
    spanning two lines.

    Parameters
    ----------
    dataset
        Input dataset.
    """  # noqa: D205
    return dataset


def test_callable_reference_captures_docstring_summary() -> None:
    reference = ref.function(_documented, kind="vectorize")

    assert reference.description == "Summary line spanning two lines."


def test_explicit_description_overrides_docstring_summary() -> None:
    reference = ref.function(_documented, kind="vectorize", description="Custom text.")

    assert reference.description == "Custom text."


def _undocumented(dataset: object) -> object:
    return dataset


def test_undocumented_callable_and_string_references_have_no_description() -> None:
    assert ref.function(_undocumented, kind="vectorize").description is None
    assert ref.function("math:ceil").description is None


def test_description_survives_conversion_to_exported_document() -> None:
    reference = ref.function(_documented, kind="vectorize")
    declaration = _dataset(
        assembly.Operator(
            id="calculate",
            interface=assembly.Interface(
                outputs=[],
            ),
            compute=assembly.Binding(
                function=reference,
                arguments={},
            ),
        ),
    )

    payload = conversion.to_dict(profiles=[declaration])
    reloaded = spec_model.Spec.model_validate(json.loads(json.dumps(payload)))

    assert payload["functions"]["_documented"]["description"] == (
        "Summary line spanning two lines."
    )
    assert reloaded.functions["_documented"].description == "Summary line spanning two lines."


def test_function_reference_rejects_non_string_description() -> None:
    with pytest.raises(TypeError, match="description must be a string"):
        ref.function("math:ceil", description=typing.cast(str, 1))


def test_function_model_defaults_signature_validation_and_exposes_schema() -> None:
    function = spec_model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns="dataframe",
        entrypoint="unavailable_package:calculate",
    )

    assert function.validate_signature is True
    assert function.name == "Calculate"
    assert function.model_dump()["validate_signature"] is True
    assert function.model_dump()["name"] == "Calculate"
    schema = spec_model.FunctionTemplate.model_json_schema()
    assert schema["properties"]["validate_signature"]["type"] == "boolean"
    assert schema["properties"]["validate_signature"]["default"] is True


def test_function_model_preserves_explicit_name() -> None:
    function = spec_model.FunctionTemplate(
        id="calculate_sum",
        name="Total Calculator",
        kind="vectorize",
        returns="dataframe",
        entrypoint="unavailable_package:calculate",
    )

    assert function.name == "Total Calculator"


def test_conflicting_signature_validation_settings_are_rejected() -> None:
    declarations = [
        profile.Profile(
            id=identifier,
            assembly=[
                assembly.Operator(
                    id="ceil",
                    interface=assembly.Interface(
                        inputs=[],
                        outputs=[],
                    ),
                    compute=assembly.Binding(
                        function=ref.function(
                            "math:ceil", kind="vectorize", validate_signature=validate_signature
                        ),
                        arguments={},
                    ),
                )
            ],
        )
        for identifier, validate_signature in [("first", True), ("second", False)]
    ]

    with pytest.raises(ValueError, match="Conflicting function definition for 'ceil'"):
        conversion.to_dict(profiles=declarations)


@pytest.mark.parametrize("location", MODULE_LOCATIONS)
def test_string_locations_are_preserved_without_importing(
    location: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail("Creating or exporting a function reference must not import its module")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    reference = ref.function(f"{location}:ceil", kind="vectorize")
    declaration = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="ceil",
                interface=assembly.Interface(
                    outputs=[],
                ),
                compute=assembly.Binding(
                    function=reference,
                    arguments={"x": 1.2},
                ),
            )
        ],
    )

    payload = conversion.to_dict(profiles=[declaration])

    assert payload["functions"]["ceil"]["entrypoint"] == f"{location}:ceil"
    assert payload["profiles"]["observations"]["assembly"]["ceil"]["compute"] == {
        "function": "ceil",
        "args": {"x": 1.2},
    }


@pytest.mark.parametrize("kind", MAPPING_KINDS)
def test_generic_mapping_exports_function_kind_without_importing(
    kind: functions.FunctionKindId, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail(f"Unexpected function import during authoring: {_args!r} {_kwargs!r}")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    declaration = _dataset(
        assembly.Operator(
            id="calculate",
            interface=assembly.Interface(
                inputs=[],
                outputs=[],
            ),
            compute=assembly.Binding(
                function=ref.function("unavailable_package.functions:calculate", kind=kind),
                arguments={"dataset": ref.profile().data},
            ),
        ),
    )

    catalog = declaration.function_catalog()

    assert catalog["calculate"].kind == kind
    expected_returns = {
        "write": "none",
        "escape": "any",
    }.get(kind, "dataframe")
    assert catalog["calculate"].returns == expected_returns
    assert catalog["calculate"].entrypoint == "unavailable_package.functions:calculate"


def test_generic_mapping_requires_operation_metadata() -> None:
    with pytest.raises(ValueError, match="kind"):
        assembly.Operator(
            id="operator",
            interface=assembly.Interface(
                inputs=[],
                outputs=[],
            ),
            compute=assembly.Binding(
                function=ref.function("math:ceil"),
                arguments={"x": 1.2},
            ),
        )


def test_escape_catalog_metadata_survives_json_round_trip() -> None:
    declaration = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="external_update",
                interface=assembly.Interface(
                    inputs=[],
                    outputs=[],
                ),
                compute=assembly.Binding(
                    function=ref.function("math:ceil", kind="escape"),
                    arguments={},
                ),
            )
        ],
    )

    payload = conversion.to_dict(profiles=[declaration])
    reloaded = spec_model.Spec.model_validate(json.loads(json.dumps(payload)))

    assert payload["functions"]["ceil"]["kind"] == "escape"
    assert payload["functions"]["ceil"]["returns"] == "any"
    assert reloaded.functions["ceil"].kind == "escape"
    assert reloaded.functions["ceil"].returns == "any"


@pytest.mark.parametrize("kind", MAPPING_KINDS)
def test_generic_mapping_accepts_function_kind_metadata(
    kind: functions.FunctionKindId,
) -> None:
    declaration = assembly.Operator(
        id="declaration",
        interface=assembly.Interface(
            inputs=[],
            outputs=[],
        ),
        compute=assembly.Binding(
            function=ref.function("math:ceil", kind=kind),
            arguments={"x": 1.2},
        ),
    )

    assert declaration.kind == kind


@pytest.mark.parametrize("kind", MAPPING_KINDS)
def test_references_supply_function_names_as_catalog_ids(kind: functions.FunctionKindId) -> None:
    declaration = assembly.Operator(
        id="declaration",
        interface=assembly.Interface(
            outputs=[],
        ),
        compute=assembly.Binding(
            function=ref.function("math:ceil", kind=kind),
            arguments={"x": 1.2},
        ),
    )
    catalog = _dataset(declaration).function_catalog()
    identifier = "ceil"

    assert catalog[identifier].kind == kind
    assert catalog[identifier].entrypoint == "math:ceil"
    assert catalog[identifier].args["x"].type == "float"
    model = declaration.to_model()
    assert model.id == declaration.id
    assert model.compute.function == identifier
    assert model.compute.args == {"x": 1.2}


def test_nested_bindings_use_reference_names_and_overrides() -> None:
    binding = bind.bind(
        ref.function("math:ceil"),
        x=bind.bind(ref.function(math.floor), function_id="rounded", x=1.2),
    )

    assert binding_conversion.to_value(binding.args) == {
        "x": {"function": "rounded", "args": {"x": 1.2}}
    }


@pytest.mark.parametrize("entrypoint", ["", "ceil", "math.ceil", "path/to/module.py"])
def test_entrypoints_require_a_module_and_function_separator(entrypoint: str) -> None:
    with pytest.raises(ValueError, match="module.path:qualname"):
        ref.function(entrypoint)


@pytest.mark.parametrize("module", ["", "  "])
def test_empty_module_locations_are_rejected(module: str) -> None:
    with pytest.raises(ValueError, match="importable dotted module name"):
        ref.function(f"{module}:ceil")


@pytest.mark.parametrize("function", [None, 42, object(), math])
def test_invalid_function_types_are_rejected(function: typing.Any) -> None:
    with pytest.raises(TypeError, match="callable or a string"):
        ref.function(function)


@pytest.mark.parametrize("name", ["", "  ", "ceil()", "a..b", "<lambda>"])
def test_invalid_function_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="Python qualified name"):
        ref.function(f"math:{name}")


@pytest.mark.parametrize(
    "location",
    [
        "functions/calculation.py",
        "package.py",
        "./functions/calculation.py",
        "/opt/spec/calculation.py",
        "https://example.org/calculation.py",
        "s3://bucket/calculation.py",
    ],
)
def test_non_import_module_locations_are_rejected(location: str) -> None:
    with pytest.raises(ValueError, match="importable dotted module name"):
        ref.function(f"{location}:calculate")


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
    with pytest.raises(ValueError, match="Python qualified name"):
        ref.function(lambda: None)


@pytest.mark.parametrize("factory", [bind.bind, bind.Bind])
@pytest.mark.parametrize("function", [math.ceil, "ceil", None])
def test_bind_requires_a_function_reference(factory: typing.Any, function: typing.Any) -> None:
    with pytest.raises(TypeError, match=r"ref.function\(callable_or_entrypoint\)"):
        factory(function, args={}) if factory is bind.Bind else factory(function)
