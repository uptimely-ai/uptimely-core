"""Explorer presentation respects disabled Python signature validation."""

import pathlib
import sys

import pytest
from support import examples as example_support

from uptimely import compiler, spec
from uptimely.explorer import presentation

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


def test_disabled_signature_does_not_import_entrypoint_module(
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
    function = definition.functions["ratio"]
    function.entrypoint = "signature_validation_fixture.calculation:calculate"
    function.validate_signature = False

    compiled = compiler.Compiler().compile(definition)
    invocation = next(item for item in compiled.invocations if item.function_id == function.id)
    data = presentation.build_presentation_data(definition, compiled)
    function_data = data["catalogs"]["configuration"]["functions"]["ratio"]
    step = next(
        step
        for stage in data["stages"]
        for step in stage["steps"]
        if step["function"] == function.id
    )

    assert not marker.exists()
    assert "signature_validation_fixture" not in sys.modules
    assert invocation.return_type is None
    assert invocation.input_features
    assert step["returns"]["type"]["engine"] is None
    assert function_data["signature_validation_disabled"]
    assert function_data["entrypoint"] == function.entrypoint
    assert function_data["args"]
