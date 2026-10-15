import math
import pathlib

import pytest

from uptimely import compile, spec
from uptimely.compile import entrypoint as compile_entrypoint
from uptimely.spec.python_spec import ref

SPEC_PATH = (
    pathlib.Path(__file__).parents[3]
    / "examples"
    / "pump_analytics"
    / "_generated"
    / "spec"
    / "spec.json"
)


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        compile.Compiler(SPEC_PATH, features="health_signal_normalized")


@pytest.mark.parametrize(
    ("category", "function_id"),
    [("vectorize", "pressure_flow_efficiency"), ("collapse", "maximum")],
)
def test_compiler_rejects_missing_function_entrypoints(category: str, function_id: str) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    getattr(specification.functions, category)[function_id].entrypoint = ""

    with pytest.raises(ValueError, match=f"Missing entrypoint for function: {function_id}"):
        compile.Compiler(specification).compile()


def test_compiler_reports_unreadable_function_signatures() -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.functions.vectorize["pressure_flow_efficiency"].entrypoint = "invalid-entrypoint"

    with pytest.raises(ValueError, match="Could not read signature.*Invalid entrypoint"):
        compile.Compiler(specification).compile()


@pytest.mark.parametrize(
    ("entrypoint", "error"),
    [
        ("invalid-entrypoint", ValueError),
        ("uptimely.plan.models:not_a_function", AttributeError),
    ],
)
def test_load_callable_rejects_invalid_entrypoints(
    entrypoint: str,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        compile_entrypoint.load_callable(entrypoint)


def test_load_callable_accepts_a_function_reference_entrypoint() -> None:
    reference = ref.function(math.ceil)

    assert compile_entrypoint.load_callable(reference.entrypoint)(1.2) == 2


@pytest.mark.parametrize("relative", [False, True])
def test_load_callable_accepts_local_file_references(
    tmp_path: pathlib.Path, relative: bool
) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("def increment(value: int) -> int:\n    return value + 1\n")
    location = "./calculation.py" if relative else str(path)
    reference = ref.function(f"{location}:increment")

    function = compile_entrypoint.load_callable(reference.entrypoint, root=tmp_path)

    assert function(2) == 3
    assert compile_entrypoint.load_callable(reference.entrypoint, root=tmp_path) is function
    assert compile_entrypoint.read_signature(reference.entrypoint, root=tmp_path).returns == "int"


@pytest.mark.parametrize(
    "location",
    [
        "https://example.org/calculation.py",
        "https://example.org/team/repository.git",
        "git+https://example.org/team/repository.git",
        "git@example.org:team/repository.git",
    ],
)
def test_remote_references_are_not_loaded(location: str) -> None:
    reference = ref.function(f"{location}:calculate")

    with pytest.raises(ValueError, match="Remote function references cannot be loaded"):
        compile_entrypoint.load_callable(reference.entrypoint)


def test_local_file_import_failures_are_not_cached(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("raise RuntimeError('module failed')\n")
    reference = ref.function(f"{path}:calculate")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="module failed"):
            compile_entrypoint.load_callable(reference.entrypoint)


def test_load_callable_rejects_noncallable_attributes() -> None:
    with pytest.raises(TypeError, match="is not callable"):
        compile_entrypoint.load_callable("math:pi")
