"""Pytest fixtures and lifecycle hooks for isolated test artifacts."""

import os
import pathlib
import shutil
import tempfile

import pytest
from support import examples, execution

_ORIGINAL_EXAMPLES_ROOT = os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT")
_TEST_ROOT: pathlib.Path | None = None


@pytest.fixture(scope="session")
def example_projects() -> pathlib.Path:
    """Prepare artifacts for tests that access example paths directly."""
    examples.prepare_example_projects(examples.EXAMPLES_ROOT)
    return examples.EXAMPLES_ROOT


def pytest_configure(config: pytest.Config) -> None:
    """Reserve a shared location without copying or building examples."""
    global _TEST_ROOT

    if hasattr(config, "workerinput"):
        return

    _TEST_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-core-tests-"))
    examples.EXAMPLES_ROOT = _TEST_ROOT / "examples"
    os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = str(examples.EXAMPLES_ROOT)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the isolated example projects created for this test run."""
    examples.cleanup()
    execution.cleanup()
    if not hasattr(config, "workerinput") and _TEST_ROOT is not None:
        shutil.rmtree(_TEST_ROOT)
        if _ORIGINAL_EXAMPLES_ROOT is None:
            os.environ.pop("UPTIMELY_TEST_EXAMPLES_ROOT", None)
        else:
            os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = _ORIGINAL_EXAMPLES_ROOT
