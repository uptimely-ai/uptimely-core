"""Direct contract tests for independently callable semantic rules."""

from __future__ import annotations

import collections.abc
import dataclasses
import json

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import row_context as row_context_model
from uptimely import spec
from uptimely.spec import functions as function_kinds
from uptimely.spec import validation as spec_validation
from uptimely.spec.validation import (
    action_contracts,
    action_outputs,
    collapse_inputs,
    context,
    errors,
    functions,
    row_context,
)


def _action_contracts(
    prepared: context.SpecValidationContext,
) -> tuple[action_contracts.ActionContract, ...]:
    collapse_facts = tuple(
        collapse_inputs.iter_collapse_inputs(
            prepared.actions, prepared.dimension_ids, prepared.feature_owners
        )
    )
    return tuple(
        action_contracts.iter_action_contracts(
            prepared.actions,
            prepared.dataset,
            collapse_inputs.source_index(collapse_facts),
        )
    )


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


def test_mapping_rules_calculate_facts_from_explicit_resources(
    prepared: context.SpecValidationContext,
) -> None:
    item = next(item for item in _action_contracts(prepared) if item.source is not None)
    assert item.action.function is not None
    original = item.action.location.action.model_copy(deep=True)
    target_path = item.action.location.path
    binding_path = (*target_path, "binding", "args")
    input_path = (*target_path, "features", "inputs")

    conform = dataclasses.replace(
        item,
        action=dataclasses.replace(
            item.action, function=item.action.function.model_copy(update={"kind": "conform"})
        ),
        dataframe_arguments=(),
    )
    error = action_contracts.validate_dataset_count(conform)
    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dataset_input"
    assert error.path == binding_path

    vectorize = dataclasses.replace(
        item,
        action=dataclasses.replace(
            item.action, function=item.action.function.model_copy(update={"kind": "vectorize"})
        ),
        dataframe_arguments=(),
    )
    error = action_contracts.validate_target_input(vectorize)
    assert isinstance(error, errors.SpecError)
    assert error.path == binding_path

    write = dataclasses.replace(
        item,
        action=dataclasses.replace(
            item.action,
            function=item.action.function.model_copy(update={"kind": "write"}),
            inputs=("foreign",),
        ),
    )
    error = action_contracts.validate_local_features(write)
    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_feature_inputs"
    assert error.path == input_path

    collapse = dataclasses.replace(
        item,
        action=dataclasses.replace(
            item.action, function=item.action.function.model_copy(update={"kind": "collapse"})
        ),
        dataframe_arguments=(),
    )
    error = action_contracts.validate_collapse_source(collapse)
    assert isinstance(error, errors.SpecError)
    assert error.path == binding_path

    assert item.source is not None
    source_dataframe = next(
        argument for argument in item.dataframe_arguments if argument.source is not None
    )
    assert source_dataframe.source is not None
    collapse = dataclasses.replace(
        collapse,
        source=dataclasses.replace(item.source, dimensions=item.action.dimensions),
    )
    error = action_contracts.validate_collapse_dimensions(collapse)
    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dimensions"
    assert error.path == input_path

    conform = dataclasses.replace(
        conform,
        dataframe_arguments=(
            dataclasses.replace(
                source_dataframe,
                source=dataclasses.replace(
                    source_dataframe.source,
                    dimensions=frozenset({"different"}),
                ),
            ),
        ),
    )
    error = action_contracts.validate_conform_dimensions(conform)
    assert isinstance(error, errors.SpecError)
    assert error.path == binding_path

    expand = dataclasses.replace(
        item,
        action=dataclasses.replace(
            item.action, function=item.action.function.model_copy(update={"kind": "expand"})
        ),
    )
    error = action_contracts.validate_expand_dimensions(expand, lambda _feature: None)
    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dimensions"
    assert error.path == binding_path
    assert item.action.location.action == original


@pytest.mark.parametrize(
    ("rule", "changes", "message"),
    [
        (
            action_contracts.validate_dataframe_reference,
            {"value": 42},
            "must reference a dataset",
        ),
        (
            action_contracts.validate_dataframe_selector,
            {"value": "$datasets.missing.id"},
            "must reference a dataframe",
        ),
        (
            action_contracts.validate_dataframe_source,
            {"source": None, "source_id": "missing"},
            "references unknown dataset missing",
        ),
    ],
)
def test_dataframe_rules_return_errors(
    prepared: context.SpecValidationContext,
    rule: collections.abc.Callable[[action_contracts.DataframeInput], ValueError | None],
    changes: dict[str, object],
    message: str,
) -> None:
    argument = next(
        item.dataframe_arguments[0]
        for item in _action_contracts(prepared)
        if item.dataframe_arguments
    )

    error = rule(dataclasses.replace(argument, **changes))

    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dataset_input"
    assert error.path == argument.path
    assert message in str(error)


def test_row_context_rules_calculate_facts_from_input_resources(
    prepared: context.SpecValidationContext,
) -> None:
    action = next(item for item in prepared.actions if "timestamp" in item.dimensions)
    action.location.action.row_context = row_context_model.RowContext(
        dimension="$dimensions.timestamp",
        before=row_context_model.ContextExtent(time="1h"),
    )
    item = row_context.RowContext(action, action.location.dataset_location, prepared.model)
    assert item.source is not None

    assert row_context.validate_dataset_order(item) is None
    assert row_context.validate_dimension(item) is None
    assert row_context.validate_dimension_type(item) is None
    assert row_context.validate_dimension_order(item) is None

    unordered = dataclasses.replace(
        item,
        source=dataclasses.replace(
            item.source,
            dataset=item.source.dataset.model_copy(update={"order": []}),
        ),
    )
    assert "directional row context requires dataset order" in str(
        row_context.validate_dataset_order(unordered)
    )
    assert "must occur in dataset order" in str(row_context.validate_dimension_order(unordered))

    dimensionless = dataclasses.replace(
        item, source=dataclasses.replace(item.source, dimensions=frozenset())
    )
    assert "not in the input entity: timestamp" in str(
        row_context.validate_dimension(dimensionless)
    )

    wrong_type_model = prepared.model.model_copy(deep=True)
    wrong_type_model.dimensions["timestamp"] = wrong_type_model.dimensions["timestamp"].model_copy(
        update={"type": "string"}
    )
    wrong_type = dataclasses.replace(item, model=wrong_type_model)
    assert "context dimension must have type datetime" in str(
        row_context.validate_dimension_type(wrong_type)
    )


def test_function_rules_are_independent(
    prepared: context.SpecValidationContext,
) -> None:
    function_id, function, dataframe_inputs = next(
        item for item in functions.iter_functions(prepared.model) if item[1].kind == "vectorize"
    )
    invalid_function = function.model_copy(update={"returns": "none"})
    return_error = functions.validate_return_kind(function_id, invalid_function, dataframe_inputs)
    count_error = functions.validate_dataframe_count(function_id, function, 100)

    assert isinstance(return_error, errors.SpecError)
    assert return_error.code == "invalid_function_return_contract"
    assert "fit kind(s): write" in str(return_error)
    assert isinstance(count_error, errors.SpecError)
    assert count_error.code == "invalid_function_input_contract"


def test_function_reference_rule_uses_explicit_catalog_and_path(
    prepared: context.SpecValidationContext,
) -> None:
    item = prepared.actions[0]
    path = (*item.location.declaration_path, "binding", "function")

    assert (
        action_outputs.validate_function_reference(
            item.location.action.binding.function,
            item.location.dataset.id,
            prepared.model.functions.root,
            path,
        )
        is None
    )

    error = action_outputs.validate_function_reference(
        "missing_function",
        item.location.dataset.id,
        prepared.model.functions.root,
        path,
    )

    assert isinstance(error, errors.SpecError)
    assert error.code == "unknown_function_reference"
    assert error.path == path
    assert "missing_function" in str(error)


def test_spec_validation_reports_unknown_function_reference_at_declaration(
    prepared: context.SpecValidationContext,
) -> None:
    item = prepared.actions[0]
    action = item.location.action
    action.binding.function = "missing_function"

    with pytest.raises(errors.SpecError) as error:
        spec_validation.validate_spec(prepared.model)

    assert error.value.code == "unknown_function_reference"
    assert error.value.path == (
        *item.location.declaration_path,
        "binding",
        "function",
    )


@pytest.mark.parametrize("kind", ["conform", "collapse", "expand"])
@pytest.mark.parametrize("source_ids", [frozenset({"foreign"}), frozenset({"one", "two"})])
def test_dimensional_source_uses_feature_owners_for_every_operation(
    prepared: context.SpecValidationContext,
    kind: function_kinds.FunctionKind,
    source_ids: frozenset[str],
) -> None:
    item = next(item for item in _action_contracts(prepared) if item.source is not None)
    assert item.action.function is not None
    action = dataclasses.replace(
        item.action,
        function=item.action.function.model_copy(update={"kind": kind}),
        inputs=tuple(source_ids),
    )
    assert item.source is not None
    owners = {
        feature_id: dataclasses.replace(
            item.source,
            dataset=item.source.dataset.model_copy(update={"id": feature_id}),
        )
        for feature_id in source_ids
    }

    def owner(feature_id: str) -> context.DatasetLocation | None:
        return owners.get(feature_id)

    contract = dataclasses.replace(item, action=action)

    count_error = action_contracts.validate_input_feature_source_count(
        contract, prepared.dimension_ids, owner
    )
    source_error = action_contracts.validate_dataframe_feature_source(
        contract, prepared.dimension_ids, owner
    )

    if len(source_ids) > 1:
        assert isinstance(count_error, errors.SpecError)
        assert count_error.code == "invalid_mapping_dataset_input"
        assert count_error.path == (*action.location.path, "features", "inputs")
        assert "inputs must belong to one source dataset" in str(count_error)
        assert source_error is None
    else:
        assert count_error is None
        assert isinstance(source_error, errors.SpecError)
        assert source_error.code == "invalid_mapping_dataset_input"
        assert source_error.path == contract.dataframe_arguments[0].path
        assert "must reference its foreign source dataset foreign" in str(source_error)


@pytest.mark.parametrize("kind", ["conform", "collapse", "expand"])
def test_foreign_dataframe_rule_is_independent_of_feature_ownership(
    prepared: context.SpecValidationContext,
    kind: function_kinds.FunctionKind,
) -> None:
    item = next(item for item in _action_contracts(prepared) if item.source is not None)
    assert item.action.function is not None
    action = dataclasses.replace(
        item.action, function=item.action.function.model_copy(update={"kind": kind})
    )
    contract = dataclasses.replace(item, action=action)
    assert action_contracts.validate_foreign_dataframe(contract) is None

    dataframe = dataclasses.replace(
        contract.dataframe_arguments[0],
        source_id=action.location.dataset.id,
        source=action.location.dataset_location,
    )
    invalid = dataclasses.replace(contract, dataframe_arguments=(dataframe,))

    error = action_contracts.validate_foreign_dataframe(invalid)

    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dataset_input"
    assert error.path == dataframe.path

    def no_owner(_feature: str) -> context.DatasetLocation | None:
        return None

    assert (
        action_contracts.validate_input_feature_source_count(
            invalid, prepared.dimension_ids, no_owner
        )
        is None
    )
    assert (
        action_contracts.validate_dataframe_feature_source(
            invalid, prepared.dimension_ids, no_owner
        )
        is None
    )


@pytest.mark.parametrize("kind", ["conform", "collapse", "expand"])
def test_mapping_rules_use_operation_dataframe_counts(
    prepared: context.SpecValidationContext,
    monkeypatch: pytest.MonkeyPatch,
    kind: function_kinds.FunctionKind,
) -> None:
    item = next(item for item in _action_contracts(prepared) if item.source is not None)
    assert item.action.function is not None
    action = dataclasses.replace(
        item.action, function=item.action.function.model_copy(update={"kind": kind})
    )
    contract = dataclasses.replace(item, action=action)
    assert len(contract.dataframe_arguments) == 1

    monkeypatch.setitem(function_kinds.KIND_DATAFRAME_INPUT_COUNTS, kind, 2)

    error = action_contracts.validate_dataset_count(contract)
    assert isinstance(error, errors.SpecError)
    assert "exactly 2 foreign dataset(s)" in str(error)
    assert (
        action_contracts.validate_dataframe_feature_source(
            contract, prepared.dimension_ids, prepared.last_feature_owner
        )
        is None
    )


def test_collapse_rejects_a_source_with_fewer_dimensions(
    prepared: context.SpecValidationContext,
) -> None:
    item = next(item for item in _action_contracts(prepared) if item.source is not None)
    assert item.action.function is not None
    action = dataclasses.replace(
        item.action, function=item.action.function.model_copy(update={"kind": "collapse"})
    )
    invalid = dataclasses.replace(
        item,
        action=action,
        source=dataclasses.replace(item.source, dimensions=frozenset()),
    )

    error = action_contracts.validate_collapse_dimensions(invalid)

    assert isinstance(error, errors.SpecError)
    assert error.code == "invalid_mapping_dimensions"
    assert error.path == (*action.location.path, "features", "inputs")
