"""Compiler orchestration ordering and fail-fast behavior."""

import logging
from unittest import mock

import pytest

from uptimely import spec
from uptimely.codebase.python import entrypoint
from uptimely.compiler import compiler
from uptimely.inspector import bindings as inspector
from uptimely.spec import model as spec_model


def test_compiler_rejects_string_features_and_recovers() -> None:
    compiler_instance = compiler.Compiler()
    specification = spec.Spec()
    original_plan = compiler_instance.compile(specification)

    with pytest.raises(ValueError, match="features must be a collection"):
        compiler_instance.compile(specification, features="result")
    assert compiler_instance.__dict__ == {}

    replacement_plan = compiler_instance.compile(specification, features=[])
    assert replacement_plan == original_plan
    assert replacement_plan.invocations is not original_plan.invocations
    assert compiler_instance.__dict__ == {}


def test_compiler_reads_shared_entrypoint_signature_once_but_validates_each_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = spec_model.FunctionTemplate(
        id="first",
        returns="any",
        entrypoint="module:calculate",
    )
    second = first.model_copy(update={"id": "second"})
    implementation = mock.Mock()
    signature = entrypoint.Signature(return_annotation=float)
    implementation.read_signature.return_value = signature
    validate = mock.Mock()
    monkeypatch.setattr(inspector.BindingInspection, "inspect", validate)
    signatures = inspector.BindingInspection.inspect_spec(
        {"first": first, "second": second},
        {"module:calculate": implementation},
    )

    implementation.read_signature.assert_called_once_with()
    assert validate.call_args_list == [mock.call(), mock.call()]
    assert signatures == {"first": signature, "second": signature}


@pytest.mark.parametrize("features", [None, [], ["missing"], "result"])
def test_compiler_logs_feature_and_graph_checks_before_failure(
    caplog: pytest.LogCaptureFixture, features: list[str] | str | None
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely")
    compiler_instance = compiler.Compiler()
    specification = spec.Spec()
    caplog.clear()

    if features:
        with pytest.raises(ValueError):
            compiler_instance.compile(specification, features=features)
    else:
        compiler_instance.compile(specification, features=features)

    selection_check = "Check feature selection is a collection, not a string"
    assert caplog.messages.count(selection_check) == (1 if isinstance(features, str) else 0)
    compiler_start = (
        caplog.messages.index(selection_check)
        if isinstance(features, str)
        else len(caplog.messages)
    )
    assert caplog.messages[0] == "Start spec validation"
    assert caplog.records[0].levelno == logging.INFO
    assert caplog.messages[1] == "Check globally unique profile IDs"
    assert caplog.messages.index("Check globally unique profile IDs") < compiler_start
    assert all("\n" not in message and message == message.lstrip() for message in caplog.messages)
    if isinstance(features, str):
        assert len(caplog.messages) == compiler_start + 1
    elif features:
        assert caplog.messages[-1] == "Select requested features and prerequisite invocations"
        assert "Validate dependency graph ordering" not in caplog.messages
    else:
        assert "Validate dependency graph ordering" in caplog.messages
        assert "Parse 0 unique entrypoints" in caplog.messages
        assert caplog.messages[-1] == (
            "Validate invocation IDs, dependencies, and execution stages"
        )
        assert not any("Compiled plan:" in message for message in caplog.messages)
        caplog.clear()
        compiler_instance.compile(specification, features=features)
        assert caplog.messages.count(selection_check) == 0
