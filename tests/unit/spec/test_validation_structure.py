"""Safeguards for semantic rule interfaces and coordinator coverage."""

import ast
import contextlib
import importlib
import inspect
import json
import pathlib
import typing
from unittest import mock

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec.validation import context
from uptimely.spec.validation import spec as spec_validation

VALIDATION_PACKAGE = (
    pathlib.Path(__file__).resolve().parents[3] / "src" / "uptimely" / "spec" / "validation"
)


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
def test_domain_rules_return_optional_errors(source_path: pathlib.Path) -> None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    module = importlib.import_module(f"uptimely.spec.validation.{source_path.stem}")
    rules = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("validate_")
        and node.name not in {"validate_spec", "validate_dataset_ids"}
    ]
    for rule in rules:
        function = getattr(module, rule.name)
        hints = typing.get_type_hints(function)
        assert hints["return"] is context.ValidationResult
        assert set(hints) == set(inspect.signature(function).parameters) | {"return"}
        assert not any(
            isinstance(node, ast.Raise | ast.FunctionDef)
            for node in ast.walk(rule)
            if node is not rule
        )
        calls = [
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(rule)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
        ]
        assert not any(name.startswith("validate_") for name in calls)


def test_validation_result_represents_an_optional_error() -> None:
    assert context.ValidationResult.__value__ == ValueError | None


def test_coordinator_supplies_valid_facts_to_every_atomic_rule() -> None:
    document = spec.Spec.model_validate(
        json.loads(
            (EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json").read_text(
                encoding="utf-8"
            )
        )
    )
    prepared = context.SpecValidationContext.build(document)
    patches = []
    for path in VALIDATION_PACKAGE.glob("*.py"):
        if path.stem in {"__init__", "context", "errors", "spec"}:
            continue
        module = importlib.import_module(f"uptimely.spec.validation.{path.stem}")
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("validate_") and name != "validate_dataset_ids":
                patches.append(mock.patch.object(module, name, wraps=function))

    with contextlib.ExitStack() as stack:
        rules = [stack.enter_context(patch) for patch in patches]
        assert all(result is None for result in spec_validation._validation_results(prepared))
        assert all(rule.called for rule in rules)
