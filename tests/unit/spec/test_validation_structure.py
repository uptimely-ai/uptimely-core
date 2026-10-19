"""Structural safeguards that do not prescribe validator implementation syntax."""

import ast
import pathlib

import pytest

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
