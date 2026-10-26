"""Direct contract tests for independently callable semantic rules."""

from __future__ import annotations

import collections.abc
import dataclasses
import json

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import operations
from uptimely.spec.validation import context, errors, functions, mapping_contracts, row_context

type ContractRule = collections.abc.Callable[[context.MappingContract], ValueError | None]
type RowRule = collections.abc.Callable[[context.RowContext], ValueError | None]


@pytest.fixture
def prepared() -> context.SpecValidationContext:
    document = spec.Spec.model_validate(
        json.loads(
            (EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json").read_text(
                encoding="utf-8"
            )
        )
    )
    return context.SpecValidationContext.build(document)


@pytest.mark.parametrize(
    ("rule", "operation", "changes", "code", "path_suffix"),
    [
        (
            mapping_contracts.validate_dataset_count,
            "conform",
            {"dataset_ids": frozenset()},
            "invalid_mapping_dataset_input",
            ("binding", "args"),
        ),
        (
            mapping_contracts.validate_dataframe_features,
            "expand",
            {"unavailable_features": ("missing",)},
            "invalid_mapping_feature_inputs",
            ("features", "inputs"),
        ),
        (
            mapping_contracts.validate_target_input,
            "vectorize",
            {"target_is_input": False},
            "invalid_mapping_dataset_input",
            ("binding", "args"),
        ),
        (
            mapping_contracts.validate_local_features,
            "write",
            {"local_foreign_features": ("foreign",)},
            "invalid_mapping_feature_inputs",
            ("features", "inputs"),
        ),
        (
            mapping_contracts.validate_collapse_source,
            "collapse",
            {"dataset_ids": frozenset()},
            "invalid_mapping_dataset_input",
            ("binding", "args"),
        ),
        (
            mapping_contracts.validate_collapse_dimensions,
            "collapse",
            {"source_dimensions": None},
            "invalid_mapping_dimensions",
            ("features", "inputs"),
        ),
        (
            mapping_contracts.validate_conform_dimensions,
            "conform",
            {"input_dimensions": (frozenset({"unknown"}),)},
            "invalid_mapping_dimensions",
            ("binding", "args"),
        ),
        (
            mapping_contracts.validate_conform_entity,
            "conform",
            {"same_entity": False},
            "invalid_mapping_entity",
            ("binding", "args"),
        ),
        (
            mapping_contracts.validate_expand_dimensions,
            "expand",
            {"has_lower_feature": False},
            "invalid_mapping_dimensions",
            ("binding", "args"),
        ),
    ],
)
def test_mapping_rules_return_structured_errors_without_raising(
    prepared: context.SpecValidationContext,
    rule: ContractRule,
    operation: operations.FunctionOperation,
    changes: dict[str, object],
    code: str,
    path_suffix: tuple[str, ...],
) -> None:
    item = next(item for item in prepared.mapping_contracts if item.source is not None)
    assert item.mapping.function is not None
    mapping = dataclasses.replace(
        item.mapping, function=item.mapping.function.model_copy(update={"operation": operation})
    )
    if rule is mapping_contracts.validate_collapse_dimensions:
        changes = {"source_dimensions": mapping.dimensions}
    invalid = dataclasses.replace(item, mapping=mapping, **changes)
    original = invalid.mapping.location.mapping.model_copy(deep=True)

    error = rule(invalid)

    assert isinstance(error, errors.SpecError)
    assert error.code == code
    assert error.path == (*mapping.location.path, *path_suffix)
    assert invalid.mapping.location.mapping == original


@pytest.mark.parametrize(
    ("rule", "changes", "message"),
    [
        (
            mapping_contracts.validate_dataframe_reference,
            {"value": 42},
            "must reference a dataset",
        ),
        (
            mapping_contracts.validate_dataframe_selector,
            {"value": "$datasets.missing.id"},
            "must reference a dataframe",
        ),
        (
            mapping_contracts.validate_dataframe_source,
            {"source": None, "source_id": "missing"},
            "references unknown dataset missing",
        ),
    ],
)
def test_dataframe_rules_return_errors(
    prepared: context.SpecValidationContext,
    rule: collections.abc.Callable[[context.DataframeInput], ValueError | None],
    changes: dict[str, object],
    message: str,
) -> None:
    argument = next(item.arguments[0] for item in prepared.mapping_contracts if item.arguments)

    error = rule(dataclasses.replace(argument, **changes))

    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dataset_input"
    assert error.path == argument.path
    assert message in str(error)


@pytest.mark.parametrize(
    ("rule", "changes", "message"),
    [
        (
            row_context.validate_dataset_order,
            {"has_order": False},
            "directional row context requires dataset order",
        ),
        (
            row_context.validate_dimension,
            {"dimensions": frozenset()},
            "context dimension is not in the input entity: timestamp",
        ),
        (
            row_context.validate_dimension_type,
            {"actual_type": "string"},
            "context dimension must have type datetime",
        ),
        (
            row_context.validate_dimension_order,
            {"order_dimensions": frozenset()},
            "context dimension must occur in dataset order",
        ),
    ],
)
def test_row_context_rules_return_plain_errors(
    rule: RowRule, changes: dict[str, object], message: str
) -> None:
    item = context.RowContext(
        mapping_id="mapping",
        requires_order=True,
        has_order=True,
        dimension_reference="$dimensions.timestamp",
        dimension_id="timestamp",
        dimensions=frozenset({"timestamp"}),
        expected_type="datetime",
        actual_type="datetime",
        order_dimensions=frozenset({"$dimensions.timestamp"}),
    )
    assert rule(item) is None

    error = rule(dataclasses.replace(item, **changes))

    assert type(error) is ValueError
    assert str(error) == f"Mapping mapping {message}"


def test_function_rules_are_independent(
    prepared: context.SpecValidationContext,
) -> None:
    function_id, function, dataframe_inputs = next(
        item for item in prepared.iter_functions() if item[1].operation == "vectorize"
    )
    invalid_function = function.model_copy(update={"returns": "none"})
    return_error = functions.validate_return_kind(function_id, invalid_function, dataframe_inputs)
    count_error = functions.validate_dataframe_count(function_id, function, 100)

    assert isinstance(return_error, errors.SpecError)
    assert return_error.code == "invalid_function_return_contract"
    assert "fit operation(s): write" in str(return_error)
    assert isinstance(count_error, errors.SpecError)
    assert count_error.code == "invalid_function_input_contract"
