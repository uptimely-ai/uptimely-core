import inspect
import math
import pathlib
import sys
import types
from collections import abc

import pytest

from uptimely.codebase.python import entrypoint as shared_entrypoint
from uptimely.spec.python import ref

pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


@pytest.mark.parametrize(
    ("entrypoint", "error"),
    [
        ("invalid-entrypoint", ValueError),
        ("uptimely.plan.models:not_a_function", AttributeError),
    ],
)
def test_function_load_rejects_invalid_entrypoints(
    entrypoint: str,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        shared_entrypoint.Entrypoint(entrypoint).function.load()


def test_function_load_accepts_a_function_reference_entrypoint() -> None:
    reference = ref.function(math.ceil)

    assert shared_entrypoint.Entrypoint(reference.entrypoint).function.load()(1.2) == 2


def test_function_load_resolves_qualified_names() -> None:
    entrypoint = shared_entrypoint.Entrypoint("decimal:Decimal.from_float")

    assert entrypoint.function.load()(1.5) == 1.5


def test_function_from_callable_uses_module_and_qualified_name() -> None:
    function = shared_entrypoint.Function.from_callable(math.ceil)

    assert function.module.location == "math"
    assert function.name == "ceil"


def test_module_and_function_identity_is_immutable() -> None:
    module = shared_entrypoint.Module("math")
    function = shared_entrypoint.Function(module, "ceil")

    with pytest.raises(AttributeError):
        module.location = "decimal"
    with pytest.raises(AttributeError):
        function.name = "floor"
    with pytest.raises(AttributeError):
        function.module = shared_entrypoint.Module("decimal")


def test_entrypoint_resolve_returns_non_callable_attributes() -> None:
    entrypoint = shared_entrypoint.Entrypoint("math:pi")

    assert entrypoint.resolve() == math.pi
    with pytest.raises(ValueError, match="is not callable"):
        entrypoint.load()


def test_entrypoint_from_path_uses_dotted_module_path(tmp_path: pathlib.Path) -> None:
    entrypoint = shared_entrypoint.Entrypoint.from_path(
        tmp_path / "project" / "spec.py",
        tmp_path,
        "python_spec",
    )

    assert entrypoint.module.location == "project.spec"
    assert entrypoint.function.name == "python_spec"


def test_entrypoint_formats_module_and_function_names() -> None:
    assert shared_entrypoint.Entrypoint.format("math", "ceil") == "math:ceil"


@pytest.mark.parametrize(("module", "name"), [("", "ceil"), ("math", ""), ("math", "bad-name")])
def test_entrypoint_format_rejects_invalid_components(module: str, name: str) -> None:
    with pytest.raises(ValueError):
        shared_entrypoint.Entrypoint.format(module, name)


@pytest.mark.parametrize(
    "entrypoint",
    [
        "some_package/calculation.py:calculate",
        "./calculation.py:calculate",
        "/tmp/calculation.py:calculate",
        "https://example.org/calculation.py:calculate",
        "s3://bucket/calculation.py:calculate",
    ],
)
def test_entrypoint_rejects_local_and_remote_module_locations(entrypoint: str) -> None:
    with pytest.raises(ValueError, match="Invalid module path"):
        shared_entrypoint.Entrypoint(entrypoint)


@pytest.mark.parametrize("location", ["", " package", "package.", "package-name", "package.py"])
def test_module_rejects_invalid_locations(location: str) -> None:
    with pytest.raises(ValueError, match="importable dotted module name"):
        shared_entrypoint.Module(location)


def test_module_load_does_not_add_project_paths(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = f"entrypoint_module_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{module_name}.py").write_text("def calculate() -> int:\n    return 42\n")
    monkeypatch.setattr(sys, "path", sys.path.copy())

    with pytest.raises(ModuleNotFoundError, match=module_name):
        shared_entrypoint.Entrypoint(f"{module_name}:calculate").function.load()
    assert str(tmp_path) not in sys.path


def test_module_source_file_for_importable_module() -> None:
    module = shared_entrypoint.Entrypoint("uptimely.codebase.python.entrypoint:Entrypoint").module

    assert module.source_file == shared_entrypoint.__file__


@pytest.mark.parametrize("has_file_attribute", [False, True])
def test_module_source_file_rejects_modules_without_files(
    monkeypatch: pytest.MonkeyPatch, has_file_attribute: bool
) -> None:
    module = types.ModuleType("without_source")
    if has_file_attribute:
        module.__file__ = None
    monkeypatch.setattr(shared_entrypoint.Module, "load", lambda self: module)

    with pytest.raises(ValueError, match="does not identify its source file"):
        _ = shared_entrypoint.Module("without_source").source_file


def test_function_load_rejects_noncallable_attributes() -> None:
    with pytest.raises(TypeError, match="is not callable"):
        shared_entrypoint.Entrypoint("math:pi").function.load()


def test_entrypoint_reuses_module_and_function_but_reads_signature_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = 0

    def read(
        cls: type[shared_entrypoint.Signature], function: shared_entrypoint.Function
    ) -> shared_entrypoint.Signature:
        nonlocal reads
        reads += 1
        return cls(
            parameters={
                "value": inspect.Parameter(
                    "value",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=float,
                )
            },
            return_annotation=int,
        )

    monkeypatch.setattr(shared_entrypoint.Signature, "read", classmethod(read))
    implementation = shared_entrypoint.Entrypoint("math:ceil")

    assert implementation.module is implementation.module
    assert implementation.function is implementation.function
    assert implementation.function.module is implementation.module
    implementation.function.read_signature()
    implementation.function.read_signature()
    assert reads == 2


def test_module_reads_package_metadata_without_importing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = 0
    package = shared_entrypoint.PackageOrigin("fixture-package", "1.0")

    def read(module_path: str) -> shared_entrypoint.PackageOrigin:
        nonlocal reads
        assert module_path == "not_imported.module"
        reads += 1
        return package

    def fail_import(self: shared_entrypoint.Module) -> types.ModuleType:
        pytest.fail("Package metadata lookup must not import the module")

    monkeypatch.setattr(shared_entrypoint.PackageOrigin, "read", read)
    monkeypatch.setattr(shared_entrypoint.Module, "load", fail_import)
    module = shared_entrypoint.Module("not_imported.module")

    assert module.read_package() is package
    assert module.read_package() is package
    assert reads == 2


def test_entrypoint_load_does_not_inspect_packages_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_metadata(module_path: str) -> shared_entrypoint.PackageOrigin:
        pytest.fail("Successful resolution must not depend on package metadata")

    monkeypatch.setattr(shared_entrypoint.PackageOrigin, "read", fail_metadata)

    assert shared_entrypoint.Entrypoint("math:ceil").load()(1.2) == 2


def test_entrypoint_resolution_reports_original_error_without_package_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_metadata(module_path: str) -> shared_entrypoint.PackageOrigin:
        pytest.fail("Resolution errors must not depend on package metadata")

    monkeypatch.setattr(shared_entrypoint.PackageOrigin, "read", fail_metadata)
    implementation = shared_entrypoint.Entrypoint("math:pi")

    with pytest.raises(ValueError, match="math:pi.*not callable") as caught:
        implementation.load()

    assert isinstance(caught.value.__cause__, TypeError)
