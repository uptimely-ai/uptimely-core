import collections
import math
import pathlib
import sys
import types
from collections import abc

import pytest
from conftest import EXAMPLES_ROOT, example_bundle

from uptimely import compiler, spec
from uptimely import entrypoint as shared_entrypoint
from uptimely import execution_plan as plan
from uptimely.explorer.sections import spec as spec_render
from uptimely.spec.python import ref

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"
pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageProvenance.invalidate_cache()
    yield
    shared_entrypoint.PackageProvenance.invalidate_cache()


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        compiler.Compiler().compile(spec.load_spec(SPEC_PATH), features="health_signal_normalized")


@pytest.mark.parametrize(
    ("category", "function_id"),
    [("vectorize", "pressure_flow_efficiency"), ("collapse", "maximum")],
)
def test_compiler_rejects_missing_function_entrypoints(category: str, function_id: str) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions[function_id].entrypoint = ""

    with pytest.raises(ValueError, match=f"Missing entrypoint for function {function_id}"):
        compiler.Compiler().compile(spec_definition)


def test_compiler_reports_unreadable_function_signatures() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["pressure_flow_efficiency"].entrypoint = "invalid-entrypoint"

    with pytest.raises(
        ValueError, match="Invalid entrypoint for function pressure_flow_efficiency"
    ):
        compiler.Compiler().compile(spec_definition)


def test_explorer_context_reports_unloadable_function_modules() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions[
        "pressure_flow_efficiency"
    ].entrypoint = "uptimely_test_missing_dependency:calculate"

    with pytest.raises(ModuleNotFoundError, match="uptimely_test_missing_dependency"):
        spec_render._build_context(spec_definition, False)


def test_compiler_skips_disabled_signatures_without_changing_dependencies(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    baseline = example_bundle().execution_plan
    package_name = f"signature_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "import uptimely_test_missing_dependency\n"
        "def calculate():\n    return None\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    function = spec_definition.functions["pressure_flow_efficiency"]
    function.entrypoint = f"{package_name}.calculation:calculate"
    function.validate_signature = False

    compiled = compiler.Compiler().compile(spec_definition)

    assert not marker.exists()
    assert package_name not in sys.modules
    assert [set(stage) for stage in compiled.stages] == [set(stage) for stage in baseline.stages]
    assert len(compiled.invocations) == len(baseline.invocations)
    baseline_invocations = {node.id: node for node in baseline.invocations}
    assert {node.id for node in compiled.invocations} == set(baseline_invocations)
    for actual in compiled.invocations:
        expected = baseline_invocations[actual.id]
        assert set(actual.dependency_ids) == set(expected.dependency_ids)
        assert actual.input_features == expected.input_features
        assert actual.output_features == expected.output_features
        if actual.function_id == function.id:
            assert actual.entrypoint == function.entrypoint
            assert actual.id not in compiled.resources["signatures"]
            assert compiled.resources["entrypoint_packages"][function.entrypoint] == {
                "distribution": None,
                "version": None,
            }
        else:
            assert actual.id in compiled.resources["signatures"]

    function.validate_signature = True
    with pytest.raises(
        ValueError, match="Could not read signature.*uptimely_test_missing_dependency"
    ):
        compiler.Compiler().compile(spec_definition)


def test_compiler_still_checks_other_functions_when_a_signature_is_disabled() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["pressure_flow_efficiency"].validate_signature = False
    spec_definition.functions["maximum"].entrypoint = "uptimely_test_missing_dependency:calculate"

    with pytest.raises(ValueError, match="Could not read signature.*maximum"):
        compiler.Compiler().compile(spec_definition)


def test_compiler_still_validates_spec_when_signature_validation_is_disabled() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["pressure_flow_efficiency"].validate_signature = False
    action = (
        spec_definition.entities["pump_telemetry"]
        .datasets["pump_telemetry_dataset"]
        .actions["pressure_flow_efficiency"]
    )
    action.features.inputs = ["$features.missing_input"]

    with pytest.raises(ValueError, match="unknown input feature"):
        compiler.Compiler().compile(spec_definition)


def test_compiler_instance_can_compile_independent_specs_and_selections() -> None:
    compiler_instance = compiler.Compiler()
    spec_definition = spec.load_spec(SPEC_PATH)

    complete = compiler_instance.compile(spec_definition)
    selected = compiler_instance.compile(spec_definition, features=["health_signal_normalized"])

    assert len(complete.invocations) > len(selected.invocations)
    assert {
        feature
        for invocation in selected.invocations
        if invocation.function_kind == "vectorize"
        for feature in invocation.output_features
    } == {"health_signal_normalized"}


def test_compiler_skips_disabled_return_annotation_validation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_name = f"annotation_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        "def calculate() -> int:\n    return 1\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec_definition = spec.load_spec(SPEC_PATH)
    function = spec_definition.functions["pressure_flow_efficiency"]
    function.entrypoint = f"{package_name}.calculation:calculate"
    function.validate_signature = False

    compiler.Compiler().compile(spec_definition)

    function.validate_signature = True
    with pytest.raises(ValueError, match="Python return annotation is int"):
        compiler.Compiler().compile(spec_definition)


@pytest.mark.parametrize("validate_signature", [False, True])
def test_compiler_checks_entrypoint_syntax_when_signature_validation_is_disabled(
    validate_signature: bool,
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    function = spec_definition.functions["pressure_flow_efficiency"]
    function.entrypoint = "invalid-entrypoint"
    function.validate_signature = validate_signature

    with pytest.raises(
        ValueError,
        match="Invalid entrypoint for function pressure_flow_efficiency",
    ):
        compiler.Compiler().compile(spec_definition)


@pytest.mark.parametrize(
    ("entrypoint", "error"),
    [
        ("invalid-entrypoint", ValueError),
        ("uptimely.execution_plan.models:not_a_function", AttributeError),
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


def test_package_provenance_uses_installed_metadata_without_importing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    distribution = types.SimpleNamespace(
        metadata={"Name": "fixture-distribution"},
        version="1.2.3",
    )
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata,
        "packages_distributions",
        lambda: {"fixture_package": ["fixture-distribution"]},
    )
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata,
        "distribution",
        lambda name: distribution if name == "fixture-distribution" else None,
    )

    provenance = shared_entrypoint.PackageProvenance.read("fixture_package.module")

    assert provenance == shared_entrypoint.PackageProvenance("fixture-distribution", "1.2.3")
    assert provenance.top_level_package == "fixture_package"
    assert provenance.distribution_candidates == ("fixture-distribution",)


def test_package_provenance_exposes_package_without_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata,
        "packages_distributions",
        lambda: {},
    )

    provenance = shared_entrypoint.PackageProvenance.read("fixture_package.module")

    assert provenance.distribution is None
    assert provenance.version is None
    assert provenance.top_level_package == "fixture_package"
    assert provenance.distribution_candidates == ()


def test_package_provenance_rejects_ambiguous_namespaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata,
        "packages_distributions",
        lambda: {"shared_namespace": ["package-a", "package-b"]},
    )

    with pytest.raises(ValueError, match="Ambiguous installed package namespace"):
        shared_entrypoint.PackageProvenance.read("shared_namespace.module")


def test_package_index_is_scanned_once_across_modules_and_compilations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scans = 0

    def packages_distributions() -> dict[str, list[str]]:
        nonlocal scans
        scans += 1
        return {}

    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata, "packages_distributions", packages_distributions
    )
    shared_entrypoint.PackageProvenance.read("first_package.module")
    shared_entrypoint.PackageProvenance.read("second_package.module")
    compiler.Compiler().compile(spec.load_spec(SPEC_PATH))
    compiler.Compiler().compile(spec.load_spec(SPEC_PATH))

    assert scans == 1


def test_package_index_refreshes_when_import_path_changes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scans = 0

    def packages_distributions() -> dict[str, list[str]]:
        nonlocal scans
        scans += 1
        return {}

    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata, "packages_distributions", packages_distributions
    )
    shared_entrypoint.PackageProvenance.read("fixture_package.module")
    monkeypatch.syspath_prepend(str(tmp_path))
    shared_entrypoint.PackageProvenance.read("fixture_package.module")
    shared_entrypoint.PackageProvenance.read("fixture_package.other")

    assert scans == 2


def test_package_index_can_be_refreshed_after_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index: dict[str, list[str]] = {}
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata, "packages_distributions", lambda: dict(index)
    )
    monkeypatch.setattr(
        shared_entrypoint.importlib.metadata,
        "distribution",
        lambda name: types.SimpleNamespace(metadata={"Name": name}, version="1.2.3"),
    )
    assert shared_entrypoint.PackageProvenance.read("fixture_package").distribution is None
    index["fixture_package"] = ["fixture-distribution"]
    assert shared_entrypoint.PackageProvenance.read("fixture_package").distribution is None

    shared_entrypoint.PackageProvenance.invalidate_cache()

    assert shared_entrypoint.PackageProvenance.read("fixture_package") == (
        shared_entrypoint.PackageProvenance("fixture-distribution", "1.2.3")
    )


def test_module_source_file_for_importable_module() -> None:
    module = shared_entrypoint.Entrypoint("uptimely.entrypoint:Entrypoint").module

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


def test_entrypoint_reuses_module_function_and_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = 0

    def read(
        cls: type[shared_entrypoint.Signature], function: shared_entrypoint.Function
    ) -> shared_entrypoint.Signature:
        nonlocal reads
        reads += 1
        return cls(args={"value": "float"}, returns="int")

    monkeypatch.setattr(shared_entrypoint.Signature, "read", classmethod(read))
    implementation = shared_entrypoint.Entrypoint("math:ceil")

    assert implementation.module is implementation.module
    assert implementation.function is implementation.function
    assert implementation.function.module is implementation.module
    assert implementation.function.signature is implementation.function.signature
    assert reads == 1


def test_module_reuses_package_metadata_without_importing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = 0
    package = shared_entrypoint.PackageProvenance("fixture-package", "1.0")

    def read(module_path: str) -> shared_entrypoint.PackageProvenance:
        nonlocal reads
        assert module_path == "not_imported.module"
        reads += 1
        return package

    def fail_import(self: shared_entrypoint.Module) -> types.ModuleType:
        pytest.fail("Package metadata lookup must not import the module")

    monkeypatch.setattr(shared_entrypoint.PackageProvenance, "read", read)
    monkeypatch.setattr(shared_entrypoint.Module, "load", fail_import)
    module = shared_entrypoint.Module("not_imported.module")

    assert module.package is package
    assert module.package is package
    assert reads == 1


def test_compiler_inspects_each_distinct_entrypoint_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: collections.Counter[str] = collections.Counter()
    original_read = shared_entrypoint.Signature.read

    def read(
        cls: type[shared_entrypoint.Signature], function: shared_entrypoint.Function
    ) -> shared_entrypoint.Signature:
        reads[f"{function.module.location}:{function.name}"] += 1
        return original_read(function)

    monkeypatch.setattr(shared_entrypoint.Signature, "read", classmethod(read))

    compiled = compiler.Compiler().compile(spec.load_spec(SPEC_PATH))

    assert len(compiled.invocations) > len(reads)
    assert reads
    assert all(count == 1 for count in reads.values())
    restored = plan.from_dict(plan.to_dict(compiled))
    assert restored.resources == compiled.resources
    assert set(restored.resources["entrypoint_packages"]) == {
        node.entrypoint for node in compiled.invocations
    }


@pytest.mark.parametrize(
    ("package", "expected"),
    [
        (shared_entrypoint.PackageProvenance(None, None), "unavailable"),
        (shared_entrypoint.PackageProvenance("fixture-package", None), "fixture-package"),
        (shared_entrypoint.PackageProvenance("fixture-package", "1.0"), "fixture-package==1.0"),
    ],
)
def test_package_provenance_display(
    package: shared_entrypoint.PackageProvenance, expected: str
) -> None:
    assert str(package) == expected


def test_entrypoint_load_does_not_inspect_packages_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_metadata(module_path: str) -> shared_entrypoint.PackageProvenance:
        pytest.fail("Successful resolution must not depend on package metadata")

    monkeypatch.setattr(shared_entrypoint.PackageProvenance, "read", fail_metadata)

    assert shared_entrypoint.Entrypoint("math:ceil").load()(1.2) == 2


def test_entrypoint_keeps_its_own_saved_package_provenance() -> None:
    package = shared_entrypoint.PackageProvenance("recorded-package", "1.0")
    implementation = shared_entrypoint.Entrypoint("math:ceil", package=package)
    other = shared_entrypoint.Entrypoint("math:floor")

    assert implementation.package is package
    assert other.package is None
    assert implementation.load()(1.2) == 2


@pytest.mark.parametrize(
    "metadata_error",
    [
        ValueError("Ambiguous installed package namespace: package-a, package-b"),
        shared_entrypoint.importlib.metadata.PackageNotFoundError("missing-package"),
    ],
)
def test_entrypoint_resolution_preserves_original_error_when_metadata_fails(
    monkeypatch: pytest.MonkeyPatch, metadata_error: Exception
) -> None:
    def fail_metadata(module_path: str) -> shared_entrypoint.PackageProvenance:
        raise metadata_error

    monkeypatch.setattr(shared_entrypoint.PackageProvenance, "read", fail_metadata)
    recorded = shared_entrypoint.PackageProvenance("recorded-package", "1.0")
    implementation = shared_entrypoint.Entrypoint("math:pi", package=recorded)

    with pytest.raises(ValueError, match="math:pi.*not callable") as caught:
        implementation.load()

    assert isinstance(caught.value.__cause__, TypeError)
    assert "recorded-package==1.0" in str(caught.value)
    assert f"available runtime package: unresolved ({metadata_error})" in str(caught.value)
