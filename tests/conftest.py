"""Shared test setup: make example modules importable from the repository root."""

import pathlib
import sys

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
EXAMPLE_SPEC_DIRS = [
    REPOSITORY_ROOT / "examples" / "example_1" / "spec",
    REPOSITORY_ROOT / "examples" / "example_2" / "spec",
]

for path in [str(REPOSITORY_ROOT), *(str(directory) for directory in EXAMPLE_SPEC_DIRS)]:
    if path not in sys.path:
        sys.path.insert(0, path)


def pytest_configure(config: pytest.Config) -> None:
    """Export the example specifications required by the test suite."""
    if hasattr(config, "workerinput"):
        return

    from examples.example_1.run_export_spec import main as export_example_1
    from examples.example_2.run_export_spec import main as export_example_2

    export_example_1()
    export_example_2()
