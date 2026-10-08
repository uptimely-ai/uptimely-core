from pathlib import Path

import pytest

from uptimely.compile import Compiler
from uptimely.compile.entrypoint import load_callable
from uptimely.spec import Specification

SPEC_PATH = (
    Path(__file__).parents[3] / "examples" / "example_1" / "generated" / "spec" / "spec.json"
)


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        Compiler(SPEC_PATH, features="health_signal_normalized")


def test_compiler_rejects_missing_function_entrypoints() -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.functions.vectorize["pressure_flow_efficiency"].entrypoint = ""

    with pytest.raises(
        ValueError, match="Missing entrypoint for function: pressure_flow_efficiency"
    ):
        Compiler(specification).compile()


def test_compiler_reports_unreadable_function_signatures() -> None:
    specification = Specification.from_json(SPEC_PATH)
    specification.functions.vectorize["pressure_flow_efficiency"].entrypoint = "invalid-entrypoint"

    with pytest.raises(ValueError, match="Could not read signature.*Invalid entrypoint"):
        Compiler(specification).compile()


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
        load_callable(entrypoint)
