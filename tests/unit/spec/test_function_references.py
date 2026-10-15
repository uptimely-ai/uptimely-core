import dataclasses
import importlib
import math
import typing
from collections import abc

import pytest

from uptimely.analytics.json import json_functions
from uptimely.analytics.python import bind, dataset, mapping, ref

MODULE_LOCATIONS = [
    "math",
    "functions/calculation.py",
    "./functions/calculation.py",
    "/opt/analytics/calculation.py",
    "https://example.org/calculation.py",
    "https://example.org/team/repository.git",
    "git@example.org:team/repository.git",
]
MAPPING_TYPES = [
    mapping.Read,
    mapping.Write,
    mapping.Vectorize,
    mapping.Collapse,
    mapping.Expand,
    mapping.Conform,
]


@pytest.mark.parametrize("function", [math.ceil, "math:ceil"])
def test_callable_and_string_forms_have_identical_entrypoints(
    function: abc.Callable[..., object] | str,
) -> None:
    reference = ref.function(function)

    assert reference.module == "math"
    assert reference.name == "ceil"
    assert reference.entrypoint == "math:ceil"
    with pytest.raises(dataclasses.FrozenInstanceError):
        reference.name = "floor"


@pytest.mark.parametrize("location", MODULE_LOCATIONS)
def test_string_locations_are_preserved_without_importing(
    location: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_import(*_args: object, **_kwargs: object) -> typing.NoReturn:
        pytest.fail("Creating or exporting a function reference must not import its module")

    monkeypatch.setattr(importlib, "import_module", unexpected_import)
    reference = ref.function(f"{location}:ceil")
    declaration = dataset.Dataset(
        id="observations",
        mappings=[mapping.Vectorize(bind=bind.bind(reference, x=1.2))],
    )

    payload = json_functions.python_to_spec_dict(datasets=[declaration])

    assert payload["functions"]["vectorize"]["ceil"]["entrypoint"] == f"{location}:ceil"
    assert payload["entities"]["entity"]["datasets"][0]["mappings"]["ceil"]["binding"] == {
        "function": "ceil",
        "args": {"x": 1.2},
    }


@pytest.mark.parametrize("mapping_type", MAPPING_TYPES)
@pytest.mark.parametrize("function_id", [None, "rounded"])
def test_references_supply_catalog_ids_and_preserve_overrides(
    mapping_type: typing.Any, function_id: str | None
) -> None:
    binding = bind.bind(ref.function("math:ceil"), function_id=function_id, x=1.2)
    declaration = mapping_type(id="calculate", bind=binding)
    catalog = dataset.Dataset(id="values", mappings=[declaration]).function_catalog()
    identifier = function_id or "ceil"
    category = mapping_type.__name__.lower()

    assert getattr(catalog, category)[identifier].entrypoint == "math:ceil"
    assert getattr(catalog, category)[identifier].args["x"].type == "float"
    model = declaration.to_model()
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
