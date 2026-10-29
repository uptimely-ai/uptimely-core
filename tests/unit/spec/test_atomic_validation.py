"""Direct raising-rule contracts against a complete example spec."""

import json

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import functions as function_kinds
from uptimely.spec.validation import errors, traversal
from uptimely.spec.validation import spec as spec_validation
from uptimely.spec.validation.rules import action_contracts, action_outputs, functions


@pytest.fixture
def document() -> spec.Spec:
    return spec.Spec.model_validate(
        json.loads(
            (EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json").read_text(
                encoding="utf-8"
            )
        )
    )


@pytest.mark.parametrize("use_runner", [False, True])
def test_unknown_function_error_uses_declaration_path(
    document: spec.Spec, use_runner: bool
) -> None:
    item = next(traversal.iter_actions(document))
    item.location.action.binding.function = "missing_function"
    validate = (
        spec_validation.validate_spec if use_runner else action_outputs.validate_function_reference
    )
    with pytest.raises(errors.SpecError) as error:
        validate(document)
    assert error.value.code == "unknown_function_reference"
    assert error.value.path == (*item.location.declaration_path, "binding", "function")
    assert "missing_function" in str(error.value)


def test_function_rules_raise_independently(document: spec.Spec) -> None:
    function = next(f for f in document.functions.root.values() if f.kind == "vectorize")
    function.returns = "none"
    assert functions.validate_dataframe_count(document) is None
    with pytest.raises(errors.SpecError) as error:
        functions.validate_return_kind(document)
    assert error.value.code == "invalid_function_return_contract"
    assert "fit kind(s): write" in str(error.value)

    function.returns = "dataframe"
    function.args.clear()
    assert functions.validate_return_kind(document) is None
    with pytest.raises(errors.SpecError) as error:
        functions.validate_dataframe_count(document)
    assert error.value.code == "invalid_function_input_contract"


@pytest.mark.parametrize("kind", ["conform", "collapse", "expand"])
def test_mapping_rules_use_shared_operation_dataframe_counts(
    document: spec.Spec, monkeypatch: pytest.MonkeyPatch, kind: function_kinds.FunctionKind
) -> None:
    function = next(f for f in document.functions.root.values() if f.kind == "collapse")
    function.kind = kind
    monkeypatch.setitem(function_kinds.KIND_DATAFRAME_INPUT_COUNTS, kind, 2)

    with pytest.raises(errors.SpecError, match=r"exactly 2 foreign dataset\(s\)") as error:
        action_contracts.validate_dataset_count(document)
    assert error.value.code == "invalid_mapping_dataset_input"
    assert error.value.path[-2:] == ("binding", "args")
