"""Isolate generated example builds and expose the example packages to tests."""

import os
import pathlib
import shutil
import sys
import tempfile

import pytest

from uptimely import compiler, spec
from uptimely import project as project_module
from uptimely.explorer import explorer

REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
EXAMPLES_ROOT = pathlib.Path(
    os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT", REPOSITORY_ROOT / "examples")
)
_ORIGINAL_EXAMPLES_ROOT = os.environ.get("UPTIMELY_TEST_EXAMPLES_ROOT")
_TEST_ROOT: pathlib.Path | None = None


def render_explorer(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Render a test website with an explicitly compiled execution plan."""
    plan = compiler.Compiler(spec_definition).compile()
    return explorer.Explorer(spec_definition, plan=plan).create_html(
        output_path, include_generated_at
    )


def pytest_configure(config: pytest.Config) -> None:
    """Build example bundles required by tests that exercise saved artifacts."""
    global EXAMPLES_ROOT, _TEST_ROOT

    if hasattr(config, "workerinput"):
        sys.path.insert(0, str(EXAMPLES_ROOT.parent))
        return

    _TEST_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-core-tests-"))
    EXAMPLES_ROOT = _TEST_ROOT / "examples"
    shutil.copytree(
        REPOSITORY_ROOT / "examples",
        EXAMPLES_ROOT,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = str(EXAMPLES_ROOT)
    sys.path.insert(0, str(_TEST_ROOT))

    for example in ("pump_analytics", "simple_analytics"):
        project_module.build_project(EXAMPLES_ROOT / example)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the isolated example projects created for this test run."""
    if not hasattr(config, "workerinput") and _TEST_ROOT is not None:
        shutil.rmtree(_TEST_ROOT)
        if _ORIGINAL_EXAMPLES_ROOT is None:
            os.environ.pop("UPTIMELY_TEST_EXAMPLES_ROOT", None)
        else:
            os.environ["UPTIMELY_TEST_EXAMPLES_ROOT"] = _ORIGINAL_EXAMPLES_ROOT
