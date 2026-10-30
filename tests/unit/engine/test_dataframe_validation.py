"""Dataframe validation dependency ordering and fail-fast behavior."""

import dataclasses
import graphlib
import types

import polars as pl
import pytest

from uptimely import execution_plan, spec
from uptimely.engine.dataframe import backend
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.engine.runtime import state
from uptimely.spec import functions


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
    assert dependencies[dataframe_validation.validate_row_count] == (
        dataframe_validation.validate_dimension_columns,
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
    assert (
        dataframe_validation.validate_row_count
        not in dependencies[dataframe_validation.validate_key_coverage]
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


def _vectorize_frame_context(
    frame: pl.DataFrame, comparison_frame: pl.DataFrame | None
) -> dataframe_validation.FrameValidationContext:
    spec_definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "kind": "vectorize",
                    "returns": "dataframe",
                    "entrypoint": "test:calculate",
                }
            }
        }
    )
    invocation = execution_plan.Invocation(
        id="invocation",
        function_kind="vectorize",
        entrypoint="test:calculate",
        function_id="calculate",
        mapping_id="calculate",
        entity_id="entity",
        dataset_id="dataset",
    )
    return dataframe_validation.FrameValidationContext(
        backend.PolarsBackend(),
        spec_definition,
        frame,
        ["key"],
        "Fragment",
        invocation=invocation,
        comparison_frame=comparison_frame,
    )


def test_equal_row_count_does_not_prove_identical_keys() -> None:
    context = _vectorize_frame_context(
        pl.DataFrame({"key": ["new"]}), pl.DataFrame({"key": ["existing"]})
    )

    assert dataframe_validation.validate_row_count(context) is None
    with pytest.raises(ValueError, match="preserve the dataset dimension keys"):
        dataframe_validation.validate_key_coverage(context)


def test_row_count_policy_is_independent_of_key_identity() -> None:
    context = _vectorize_frame_context(
        pl.DataFrame({"key": ["existing", "new"]}), pl.DataFrame({"key": ["existing"]})
    )

    with pytest.raises(ValueError, match="preserve the accumulated dataset row count"):
        dataframe_validation.validate_row_count(context)
    with pytest.raises(ValueError, match="preserve the dataset dimension keys"):
        dataframe_validation.validate_key_coverage(context)


def test_structural_policy_changes_apply_without_changing_kind_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _vectorize_frame_context(
        pl.DataFrame({"key": ["new", "another"]}), pl.DataFrame({"key": ["existing"]})
    )
    definitions = dict(functions.FUNCTION_KINDS)
    definitions[functions.VECTORIZE] = dataclasses.replace(
        definitions[functions.VECTORIZE],
        row_count_relation="unrestricted",
        key_relation="unrestricted",
    )
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    assert dataframe_validation.validate_row_count(context) is None
    assert dataframe_validation.validate_key_coverage(context) is None


def test_key_identity_requires_the_accumulated_target() -> None:
    context = _vectorize_frame_context(pl.DataFrame({"key": ["new"]}), None)

    with pytest.raises(ValueError, match="preserve the dataset dimension keys"):
        dataframe_validation.validate_key_coverage(context)
