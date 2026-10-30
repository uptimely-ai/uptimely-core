"""Optional implementation semantics and explicit function-reference contracts."""

import importlib
import typing

import pytest

from uptimely.spec import functions as function_kinds
from uptimely.spec import python as authoring
from uptimely.spec.python import functions, ref


def implementation(value: str) -> str:
    return value


@authoring.function(kind="vectorize")
def decorated(value: str) -> str:
    return value


@pytest.mark.parametrize("kind", function_kinds.FUNCTION_KINDS)
def test_decorator_preserves_callable_identity_and_behavior(
    kind: function_kinds.FunctionKindId,
) -> None:
    def original(value: str) -> str:
        return value

    result = functions.function(kind=kind)(original)
    assert result is original
    assert result("value") == "value"
    assert functions.declared_kind(result) == kind


def test_public_decorator_and_module_exports_are_unambiguous() -> None:
    module = importlib.import_module("uptimely.spec.python.functions")
    assert authoring.functions is module
    assert authoring.function is module.function
    assert not hasattr(authoring, "kind")
    assert not hasattr(authoring.actions, "kind")


def test_undecorated_function_uses_explicit_reference_contract() -> None:
    assert functions.declared_kind(implementation) is None
    action = authoring.Action(
        id="calculate",
        function=ref.function(implementation, kind="vectorize"),
        arguments={"value": "input"},
        outputs=[],
    )
    assert action.kind == "vectorize"
    assert action.function_catalog()["implementation"].kind == "vectorize"
    assert action.to_model().binding.args == {"value": "input"}
    assert functions.declared_kind(implementation) is None
    assert implementation("input") == "input"


def test_decorated_direct_callable_and_reference_have_identical_contracts() -> None:
    direct = authoring.Action(
        id="calculate", function=decorated, arguments={"value": "input"}, outputs=[]
    )
    referenced = authoring.Action(
        id="calculate",
        function=ref.function(decorated),
        arguments={"value": "input"},
        outputs=[],
    )
    assert direct.kind == referenced.kind == "vectorize"
    assert direct.to_model() == referenced.to_model()
    assert direct.function_catalog() == referenced.function_catalog()
    assert ref.function(decorated, kind="vectorize").kind == "vectorize"


def test_explicit_kind_cannot_override_decorated_semantics() -> None:
    with pytest.raises(ValueError, match="conflicts with decorated kind 'vectorize'"):
        ref.function(decorated, kind="collapse")
    assert ref.function(decorated).kind == "vectorize"


def test_redecoration_rejects_conflicting_semantics() -> None:
    assert functions.function(kind="vectorize")(decorated) is decorated
    with pytest.raises(ValueError, match="conflicts with decorated kind 'vectorize'"):
        functions.function(kind="collapse")(decorated)
    assert functions.declared_kind(decorated) == "vectorize"


def test_decorator_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported function kind: unknown"):
        functions.function(kind=typing.cast(function_kinds.FunctionKindId, "unknown"))


@pytest.mark.parametrize("use_reference", [False, True])
def test_missing_function_semantics_are_not_guessed(use_reference: bool) -> None:
    target = ref.function(implementation) if use_reference else implementation
    with pytest.raises(ValueError, match="Function kind is required"):
        authoring.Action(id="calculate", function=target, arguments={"value": "input"}, outputs=[])
