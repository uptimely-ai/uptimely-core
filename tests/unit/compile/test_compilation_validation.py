"""Compiler-build validation ordering and fail-fast behavior."""

import graphlib

import pytest

from uptimely import spec
from uptimely.compiler import validation


def test_compilation_validators_follow_explicit_prerequisites_in_build_order() -> None:
    dependencies = validation.COMPILATION_VALIDATION_DEPENDENCIES
    ordered = tuple(graphlib.TopologicalSorter(dependencies).static_order())

    assert ordered == tuple(dependencies)
    assert set(dependencies) == {
        validation.validate_invocation_graph,
        validation.validate_feature_selection,
        validation.validate_schedulability,
        validation.validate_invocations,
        validation.validate_entrypoints,
        validation.validate_packages,
        validation.validate_signatures,
    }
    assert dependencies[validation.validate_feature_selection] == (
        validation.validate_invocation_graph,
    )
    assert dependencies[validation.validate_schedulability] == (
        validation.validate_feature_selection,
    )
    assert dependencies[validation.validate_invocations] == (validation.validate_feature_selection,)
    assert dependencies[validation.validate_entrypoints] == (validation.validate_feature_selection,)
    assert dependencies[validation.validate_packages] == (validation.validate_entrypoints,)
    assert dependencies[validation.validate_signatures] == (validation.validate_entrypoints,)
    assert all(
        prerequisite in dependencies
        for prerequisites in dependencies.values()
        for prerequisite in prerequisites
    )


def test_compilation_validation_stops_after_first_failed_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    seen_contexts: list[validation.CompilationContext] = []

    def failing_validator(context: validation.CompilationContext) -> None:
        calls.append("failing")
        seen_contexts.append(context)
        raise ValueError("invalid compilation")

    def dependent_validator(context: validation.CompilationContext) -> None:
        calls.append("dependent")
        seen_contexts.append(context)

    monkeypatch.setattr(
        validation,
        "COMPILATION_VALIDATION_DEPENDENCIES",
        {failing_validator: (), dependent_validator: (failing_validator,)},
    )
    context = validation.CompilationContext(spec.Spec(), None)

    with pytest.raises(ValueError, match="invalid compilation"):
        validation.validate_compilation(context)

    assert calls == ["failing"]
    assert seen_contexts == [context]
