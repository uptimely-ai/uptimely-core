import pathlib
from collections import abc

import pytest

from uptimely.codebase.python import entrypoint as shared_entrypoint
from uptimely.codebase.python import inspection

pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


def test_callable_inspection_resolves_once_and_exposes_signature_views(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "inspection_fixture.py"
    module_path.write_text(
        "def calculate(value: int) -> float:\n"
        '    """Convert a value to float."""\n'
        "    return float(value)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    implementation = shared_entrypoint.Entrypoint("inspection_fixture:calculate")
    original_load = shared_entrypoint.Function.load
    loads = 0

    def load(function: shared_entrypoint.Function) -> abc.Callable[..., object]:
        nonlocal loads
        loads += 1
        return original_load(function)

    monkeypatch.setattr(shared_entrypoint.Function, "load", load)

    result = inspection.CallableInspection.read(implementation, tmp_path)

    assert loads == 1
    assert result.source_file == str(module_path)
    assert result.source_origin == shared_entrypoint.SourceOrigin("project")
    assert result.raw_signature.parameters["value"].annotation is int
    assert result.display_signature.args == {"value": "int"}
    assert result.display_signature.returns == "float"
    assert result.docstring == "Convert a value to float."
