"""Engine-level validation dependency ordering."""

import graphlib

import pytest

from uptimely import execution_plan
from uptimely.engine import validation
from uptimely.engine.dataframe import backend


def test_engine_validation_dependencies_are_acyclic() -> None:
    dependencies = validation.ENGINE_VALIDATION_DEPENDENCIES
    ordered = tuple(graphlib.TopologicalSorter(dependencies).static_order())

    assert ordered == (validation.validate_plan_backend,)
    assert dependencies[validation.validate_plan_backend] == ()


def test_engine_validation_checks_plan_backend() -> None:
    plan = execution_plan.ExecutionPlan(3, "polars", {}, [], [])
    polars_backend = backend.PolarsBackend()

    validation.validate_engine(plan, polars_backend)

    invalid_plan = execution_plan.ExecutionPlan(3, "pandas", {}, [], [])
    with pytest.raises(ValueError, match="Unsupported plan backend: pandas"):
        validation.validate_engine(invalid_plan, polars_backend)


def test_engine_validation_stops_after_first_failed_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    seen_arguments: list[tuple[execution_plan.ExecutionPlan, backend.DataFrameBackend]] = []
    plan = execution_plan.ExecutionPlan(3, "polars", {}, [], [])
    polars_backend = backend.PolarsBackend()

    def failing_validator(
        plan: execution_plan.ExecutionPlan,
        backend_instance: backend.DataFrameBackend,
    ) -> None:
        calls.append("failing")
        seen_arguments.append((plan, backend_instance))
        raise ValueError("invalid engine configuration")

    def dependent_validator(
        plan: execution_plan.ExecutionPlan,
        backend_instance: backend.DataFrameBackend,
    ) -> None:
        calls.append("dependent")
        seen_arguments.append((plan, backend_instance))

    monkeypatch.setattr(
        validation,
        "ENGINE_VALIDATION_DEPENDENCIES",
        {failing_validator: (), dependent_validator: (failing_validator,)},
    )

    with pytest.raises(ValueError, match="invalid engine configuration"):
        validation.validate_engine(plan, polars_backend)

    assert calls == ["failing"]
    assert seen_arguments == [(plan, polars_backend)]
