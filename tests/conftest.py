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
    """Export the example specifications required by the test suite."""
    if hasattr(config, "workerinput"):
        return

    pump_spec = importlib.import_module("examples.pump_analytics.config.spec.spec")
    simple_spec = importlib.import_module("examples.simple_analytics.config.spec.spec")
    specifications = (
        (
            "pump_analytics",
            spec.Specification.from_python(
                entities=pump_spec.entities,
                dimensions=pump_spec.dimensions,
                name="Pump analytics",
            ),
        ),
        (
            "simple_analytics",
            spec.Specification.from_python(
                entities=simple_spec.python_specification.entities,
                dimensions=simple_spec.python_specification.dimensions,
                name=simple_spec.python_specification.name,
            ),
        ),
    )
    for project, specification in specifications:
        output_path = REPOSITORY_ROOT / "examples" / project / "_generated" / "spec" / "spec.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        specification.to_json(output_path)
