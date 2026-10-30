"""Dataframe validation dependency ordering and fail-fast behavior."""

import graphlib

import pytest

from uptimely import execution_plan, spec
from uptimely.engine.dataframe import backend
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.engine.runtime import state


def test_dataframe_validation_dependencies_are_complete_and_acyclic() -> None:
    dependencies = dataframe_validation.DATAFRAME_VALIDATION_DEPENDENCIES
    ordered = tuple(graphlib.TopologicalSorter(dependencies).static_order())
    position = {validator: index for index, validator in enumerate(ordered)}

    assert all(
        prerequisite in dependencies
        for prerequisites in dependencies.values()
        for prerequisite in prerequisites
    )
    assert all(
        position[prerequisite] < position[validator]
        for validator, prerequisites in dependencies.items()
        for prerequisite in prerequisites
    )
    assert dependencies[dataframe_validation.validate_input_features] == (
        dataframe_validation.validate_input_function,
    )
    assert dependencies[dataframe_validation.validate_dimension_columns] == (
        dataframe_validation.validate_frame_type,
    )
    assert dependencies[dataframe_validation.validate_unique_dimension_keys] == (
        dataframe_validation.validate_dimension_columns,
    )
    assert dependencies[dataframe_validation.validate_output_columns] == (
        dataframe_validation.validate_unique_dimension_keys,
    )
    assert dependencies[dataframe_validation.validate_fragment_declared_types] == (
        dataframe_validation.validate_output_columns,
    )
    assert dependencies[dataframe_validation.validate_key_coverage] == (
        dataframe_validation.validate_fragment_declared_types,
    )


def test_dataframe_validation_stops_after_first_failed_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    seen_contexts: list[dataframe_validation.DataFrameValidationContext] = []
    context = dataframe_validation.InputValidationContext(
        backend.PolarsBackend(),
        spec.Spec(),
        state.RuntimeState(),
        execution_plan.Invocation(
            id="invocation",
            function_kind="read",
            entrypoint="test:read",
            function_id="read",
            mapping_id="read",
            entity_id="entity",
            dataset_id="dataset",
        ),
    )

    def failing_validator(context: dataframe_validation.DataFrameValidationContext) -> None:
        calls.append("failing")
        seen_contexts.append(context)
        raise ValueError("invalid dataframe state")

    def dependent_validator(context: dataframe_validation.DataFrameValidationContext) -> None:
        calls.append("dependent")
        seen_contexts.append(context)

    monkeypatch.setattr(
        dataframe_validation,
        "DATAFRAME_VALIDATION_DEPENDENCIES",
        {failing_validator: (), dependent_validator: (failing_validator,)},
    )

    with pytest.raises(ValueError, match="invalid dataframe state"):
        dataframe_validation.validate_dataframes(context, (dependent_validator,))

    assert calls == ["failing"]
    assert seen_contexts == [context]
