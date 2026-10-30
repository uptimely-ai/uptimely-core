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
    context = validation.EngineValidationContext(
        execution_plan.ExecutionPlan(3, "polars", {}, [], []),
        backend.PolarsBackend(),
    )

    validation.validate_engine(context)

    invalid_context = validation.EngineValidationContext(
        execution_plan.ExecutionPlan(3, "pandas", {}, [], []),
        backend.PolarsBackend(),
    )
    with pytest.raises(ValueError, match="Unsupported plan backend: pandas"):
        validation.validate_engine(invalid_context)


def test_engine_validation_stops_after_first_failed_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    seen_contexts: list[validation.EngineValidationContext] = []
    context = validation.EngineValidationContext(
        execution_plan.ExecutionPlan(3, "polars", {}, [], []),
        backend.PolarsBackend(),
    )

    def failing_validator(context: validation.EngineValidationContext) -> None:
        calls.append("failing")
        seen_contexts.append(context)
        raise ValueError("invalid engine configuration")

    def dependent_validator(context: validation.EngineValidationContext) -> None:
        calls.append("dependent")
        seen_contexts.append(context)

    monkeypatch.setattr(
        validation,
        "ENGINE_VALIDATION_DEPENDENCIES",
        {failing_validator: (), dependent_validator: (failing_validator,)},
    )

    with pytest.raises(ValueError, match="invalid engine configuration"):
        validation.validate_engine(context)

    assert calls == ["failing"]
    assert seen_contexts == [context]
