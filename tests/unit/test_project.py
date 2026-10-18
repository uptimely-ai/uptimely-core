"""Tests for the fixed analytics project layout."""

import pathlib

import pytest

from uptimely import project


def test_default_analytics_attribute() -> None:
    assert project.DEFAULT_ANALYTICS_ATTRIBUTE == "python_analytics"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (project.CONFIG_DIR, "config"),
        (project.ANALYTICS_SOURCE_DIR, "config/analytics"),
        (project.ANALYTICS_PYTHON_ENTRY_FILE, "config/analytics/analytics.py"),
        (project.ANALYTICS_JSON_ENTRY_FILE, "config/analytics/analytics.json"),
        (project.COMPILER_CONFIG_FILE, "config/compiler.json"),
        (project.ENGINE_CONFIG_FILE, "config/engine.json"),
        (project.DATA_DIR, "data"),
        (project.FUNCTIONS_DIR, "functions"),
        (project.GENERATED_DIR, "_generated"),
        (project.ANALYTICS_OUTPUT_DIR, "_generated/analytics"),
        (project.ANALYTICS_JSON_FILE, "_generated/analytics/analytics.json"),
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
