"""Tests for the fixed analytics project layout."""

import pathlib

import pytest

from uptimely import project


def test_default_spec_attribute() -> None:
    assert project.DEFAULT_SPEC_ATTRIBUTE == "python_spec"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (project.CONFIG_DIR, "config"),
        (project.SPEC_SOURCE_DIR, "config/spec"),
        (project.SPEC_PYTHON_ENTRY_FILE, "config/spec/spec.py"),
        (project.SPEC_JSON_ENTRY_FILE, "config/spec/spec.json"),
        (project.COMPILER_CONFIG_FILE, "config/compiler.json"),
        (project.ENGINE_CONFIG_FILE, "config/engine.json"),
        (project.DATA_DIR, "data"),
        (project.FUNCTIONS_DIR, "functions"),
        (project.GENERATED_DIR, "_generated"),
        (project.SPEC_OUTPUT_DIR, "_generated/spec"),
        (project.SPEC_JSON_FILE, "_generated/spec/spec.json"),
        (project.COMPILE_OUTPUT_DIR, "_generated/compile"),
        (project.EXECUTION_PLAN_FILE, "_generated/compile/execution_plan.json"),
        (project.EXPLORER_OUTPUT_DIR, "_generated/explorer"),
        (project.EXPLORER_INDEX_FILE, "_generated/explorer/index.html"),
    ],
)
def test_standard_paths(path: pathlib.Path, expected: str) -> None:
    assert path == pathlib.Path(expected)
    assert not path.is_absolute()
    assert pathlib.Path("example") / path == pathlib.Path("example") / expected
