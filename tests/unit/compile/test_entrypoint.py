import pathlib

import pytest

from uptimely import compile, spec
from uptimely.compile import entrypoint as compile_entrypoint

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
