"""Safeguards for flat semantic rules and explicit dependency coverage."""

import ast
import graphlib
import importlib
import inspect
import pathlib
import typing

import pytest

from uptimely import spec
from uptimely.spec.validation import spec as spec_validation

VALIDATION_PACKAGE = pathlib.Path(inspect.getfile(spec_validation)).parent


@pytest.mark.parametrize(
    "source_path",
    sorted(VALIDATION_PACKAGE.glob("*.py")),
    ids=lambda source_path: source_path.name,
)
def test_validation_does_not_use_runtime_assertions(source_path: pathlib.Path) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    assertions = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    assert not assertions, f"{source_path.name} uses runtime assertions at {assertions}"


@pytest.mark.parametrize(
    "source_path",
    sorted(VALIDATION_PACKAGE.glob("*.py")),
    ids=lambda source_path: source_path.name,
)
def test_domain_rules_accept_only_spec_and_do_not_call_other_rules(
    source_path: pathlib.Path,
) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    module = importlib.import_module(f"uptimely.spec.validation.{source_path.stem}")
    for rule in tree.body:
        if not isinstance(rule, ast.FunctionDef) or not rule.name.startswith("validate_"):
            continue
        function = getattr(module, rule.name)
        assert typing.get_type_hints(function) == {"spec": spec.Spec, "return": type(None)}
        assert list(inspect.signature(function).parameters) == ["spec"]
        if rule.name == "validate_spec":
            continue
        assert function in spec_validation.VALIDATION_DEPENDENCIES
        assert not any(
            isinstance(node, ast.FunctionDef) for node in ast.walk(rule) if node is not rule
        )
        calls = [
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(rule)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
        ]
        assert not any(name.startswith("validate_") for name in calls)


def test_dependency_graph_registers_every_prerequisite_and_is_acyclic() -> None:
    graph = spec_validation.VALIDATION_DEPENDENCIES
    ordered = tuple(graphlib.TopologicalSorter(graph).static_order())
    assert len(ordered) == len(graph)
    positions = {rule: index for index, rule in enumerate(ordered)}
    for rule, prerequisites in graph.items():
        for prerequisite in prerequisites:
            assert prerequisite in graph
            assert positions[prerequisite] < positions[rule]
