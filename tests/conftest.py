"""Shared test setup: make example modules importable from the repository root."""

import importlib
import pathlib
import sys

import pytest

from uptimely import spec

REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
EXAMPLE_SPEC_DIRS = [
    REPOSITORY_ROOT / "examples" / "pump_analytics" / "config" / "spec",
    REPOSITORY_ROOT / "examples" / "simple_analytics" / "config" / "spec",
]

for path in [str(REPOSITORY_ROOT), *(str(directory) for directory in EXAMPLE_SPEC_DIRS)]:
    if path not in sys.path:
        sys.path.insert(0, path)


def pytest_configure(config: pytest.Config) -> None:
    """Export the example spec required by the test suite."""
    if hasattr(config, "workerinput"):
        return

    pump_analytics_module = importlib.import_module("examples.pump_analytics.config.spec.spec")
    simple_analytics_module = importlib.import_module("examples.simple_analytics.config.spec.spec")
    spec_definitions = (
        (
            "pump_analytics",
            spec.from_python(
                entities=pump_analytics_module.entities,
                dimensions=pump_analytics_module.dimensions,
                name="Pump analytics",
            ),
        ),
        (
            "simple_analytics",
            spec.from_python(
                entities=simple_analytics_module.python_spec.entities,
                dimensions=simple_analytics_module.python_spec.dimensions,
                name=simple_analytics_module.python_spec.name,
            ),
        ),
    )
    for project, spec_definition in spec_definitions:
        output_path = REPOSITORY_ROOT / "examples" / project / "_generated" / "spec" / "spec.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        spec.write_document(spec_definition, output_path)
