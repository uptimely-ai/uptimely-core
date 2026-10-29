"""Explorer behavior for functions without Python signature validation."""

import pathlib
import sys

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import compiler, spec
from uptimely.explorer import explorer
from uptimely.explorer.sections import plan as plan_render

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def test_disabled_signature_renders_without_importing_module_or_parent(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "signature_validation_fixture"
    package.mkdir()
    marker = tmp_path / "parent_imported"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    (package / "calculation.py").write_text(
        "import uptimely_test_missing_dependency\n"
        "def calculate(dataset, output):\n"
        "    return dataset\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    definition = spec.load_spec(SPEC_PATH)
    function = definition.functions["pressure_flow_efficiency"]
    function.entrypoint = "signature_validation_fixture.calculation:calculate"
    function.validate_signature = False

    compiled = compiler.Compiler().compile(definition)
    invocation = next(item for item in compiled.invocations if item.function_id == function.id)
    step = plan_render._render_step(1, invocation, compiled)
    index = explorer.Explorer(definition, plan=compiled).create_html(tmp_path / "site/index.html")
    functions_page = (index.parent / "spec/functions.html").read_text(encoding="utf-8")

    assert not marker.exists()
    assert "signature_validation_fixture" not in sys.modules
    assert invocation.id not in compiled.resources["signatures"]
    assert invocation.input_features
    assert step["returns"]["type"]["engine"] is None
    assert "Python signature validation disabled" in functions_page
    assert function.entrypoint in functions_page
    assert "Declared arguments" in functions_page
    assert "pressure_flow_efficiency</span>(" not in functions_page
