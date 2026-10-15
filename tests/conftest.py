"""Shared test setup: make example modules importable from the repository root."""

import importlib
import pathlib
import sys

import pytest

from uptimely import analytics

REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
EXAMPLE_ANALYTICS_DIRS = [
    REPOSITORY_ROOT / "examples" / "pump_analytics" / "config" / "analytics",
    REPOSITORY_ROOT / "examples" / "simple_analytics" / "config" / "analytics",
]

for path in [str(REPOSITORY_ROOT), *(str(directory) for directory in EXAMPLE_ANALYTICS_DIRS)]:
    if path not in sys.path:
        sys.path.insert(0, path)


def pytest_configure(config: pytest.Config) -> None:
    """Export the example specifications required by the test suite."""
    if hasattr(config, "workerinput"):
        return

    pump_analytics_module = importlib.import_module(
        "examples.pump_analytics.config.analytics.analytics"
    )
    simple_analytics_module = importlib.import_module(
        "examples.simple_analytics.config.analytics.analytics"
    )
    analytics_definitions = (
        (
            "pump_analytics",
            analytics.Analytics.from_python(
                entities=pump_analytics_module.entities,
                dimensions=pump_analytics_module.dimensions,
                name="Pump analytics",
            ),
        ),
        (
            "simple_analytics",
            analytics.Analytics.from_python(
                entities=simple_analytics_module.python_analytics.entities,
                dimensions=simple_analytics_module.python_analytics.dimensions,
                name=simple_analytics_module.python_analytics.name,
            ),
        ),
    )
    for project, analytics_definition in analytics_definitions:
        output_path = (
            REPOSITORY_ROOT / "examples" / project / "_generated" / "analytics" / "analytics.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        analytics_definition.to_json(output_path)
