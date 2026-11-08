"""Compiler orchestration ordering and fail-fast behavior."""

import logging
from unittest import mock

import pytest

from uptimely import entrypoint, spec
from uptimely import plan as execution_plan
from uptimely.compiler import compiler, validation
from uptimely.compiler import graph as invocation_graph
from uptimely.spec import model as spec_model


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "spec",
        "graph",
        "subset",
        "topology",
        "emit",
        "entrypoint",
        "package",
        "signature",
        "signature_validation",
    ],
)
def test_compiler_runs_explicit_steps_in_fail_fast_order(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    function = spec_model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns="dataframe",
        entrypoint="module:calculate",
    )
    specification = spec.Spec(functions={"calculate": function})
    graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    selected_graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    graph.subset.return_value = selected_graph
    node = invocation_graph.InvocationNode(
        function_id="calculate",
        profile_id="entity",
        operator_id="calculate",
        function_kind="vectorize",
    )
    selected_graph.invocations = [node]
    emitted_invocation = execution_plan.Invocation(
        id=node.node_id,
        function_kind="vectorize",
        entrypoint="module:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="entity",
    )
    operations = {
        "spec": mock.Mock(),
        "graph": mock.Mock(return_value=graph),
        "subset": graph.subset,
        "topology": mock.Mock(return_value=[[node]]),
        "emit": mock.Mock(return_value=emitted_invocation),
        "entrypoint": mock.Mock(),
        "package": mock.Mock(return_value=entrypoint.PackageProvenance(None, None)),
        "signature": mock.Mock(return_value=entrypoint.Signature(returns="float")),
        "signature_validation": mock.Mock(),
    }
    implementation = mock.Mock()
    implementation.module.read_package = operations["package"]
    implementation.function.read_signature = operations["signature"]
    operations["entrypoint"].return_value = implementation
    selected_graph.topology = operations["topology"]
    calls = mock.Mock()
    for name, operation in operations.items():
        calls.attach_mock(operation, name)
    if failure is not None:
        operations[failure].side_effect = ValueError("invalid compilation")

    monkeypatch.setattr(compiler.spec_validation, "validate_spec", operations["spec"])
    monkeypatch.setattr(invocation_graph, "InvocationGraph", operations["graph"])
    monkeypatch.setattr(compiler.plan_emission, "emit_invocation", operations["emit"])
    monkeypatch.setattr(compiler.entrypoint, "Entrypoint", operations["entrypoint"])
    monkeypatch.setattr(
        compiler.validation, "validation_callable_signature", operations["signature_validation"]
    )

    builder = compiler.Compiler()
    features = ["result", "result"]
    if failure is None:
        plan = builder.compile(specification, features=features)
    else:
        with pytest.raises(ValueError, match="invalid compilation"):
            builder.compile(specification, features=features)
    assert builder.__dict__ == {}

    expected = [
        mock.call.spec(specification),
        mock.call.graph(specification),
        mock.call.subset(["result"]),
        mock.call.topology(),
        mock.call.emit(specification, selected_graph, node),
        mock.call.entrypoint("module:calculate"),
        mock.call.package(),
        mock.call.signature(),
        mock.call.signature_validation(
            validation.CallableValidationContext(function, entrypoint.Signature(returns="float"))
        ),
    ]
    if failure is not None:
        expected = expected[: list(operations).index(failure) + 1]
    assert calls.mock_calls == expected
    if failure is None:
        assert plan.invocations == [emitted_invocation]
        assert plan.stages == [[node.node_id]]
        assert plan.resources == {
            "signatures": {node.node_id: "float"},
            "entrypoint_packages": {"module:calculate": {"distribution": None, "version": None}},
        }
        assert calls.mock_calls == expected


def test_compiler_has_no_active_build_properties() -> None:
    builder = compiler.Compiler()
    assert builder.__dict__ == {}
    assert not hasattr(builder, "graph")
    assert not hasattr(builder, "spec_definition")


def test_compiler_rejects_string_features_and_recovers() -> None:
    builder = compiler.Compiler()
    specification = spec.Spec()
    original_plan = builder.compile(specification)

    with pytest.raises(ValueError, match="features must be a collection"):
        builder.compile(specification, features="result")
    assert builder.__dict__ == {}

    replacement_plan = builder.compile(specification, features=[])
    assert replacement_plan == original_plan
    assert replacement_plan.resources is not original_plan.resources
    assert builder.__dict__ == {}


def test_compiler_inspects_unique_functions_once_and_skips_disabled_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function = spec_model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns="dataframe",
        entrypoint="module:calculate",
    )
    disabled = function.model_copy(update={"id": "disabled", "validate_signature": False})
    specification = spec.Spec(functions={"calculate": function, "disabled": disabled})
    monkeypatch.setattr(compiler.spec_validation, "validate_spec", mock.Mock())
    signature = entrypoint.Signature(returns="float")
    implementation = mock.Mock()
    implementation.module.read_package.return_value = entrypoint.PackageProvenance(None, None)
    implementation.function.read_signature.return_value = signature
    parse_entrypoint = mock.Mock(return_value=implementation)
    validate = mock.Mock()
    monkeypatch.setattr(compiler.entrypoint, "Entrypoint", parse_entrypoint)
    monkeypatch.setattr(compiler.validation, "validation_callable_signature", validate)
    nodes = [
        invocation_graph.InvocationNode(
            function_id=function_id,
            profile_id="entity",
            operator_id=operator,
            function_kind=specification.functions[function_id].kind,
        )
        for function_id, operator in [
            ("calculate", "first"),
            ("calculate", "second"),
            ("disabled", "third"),
        ]
    ]
    graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    graph.topology.return_value = [nodes]
    graph.invocations = nodes
    monkeypatch.setattr(compiler.invocation_graph, "InvocationGraph", mock.Mock(return_value=graph))
    monkeypatch.setattr(
        compiler.plan_emission,
        "emit_invocation",
        mock.Mock(
            side_effect=lambda _specification, _graph, node: execution_plan.Invocation(
                id=node.node_id,
                function_kind=node.function_kind,
                entrypoint="module:calculate",
                function_id=node.function_id,
                operator_id=node.operator_id,
                profile_id=node.profile_id,
            )
        ),
    )

    plan = compiler.Compiler().compile(specification)

    assert parse_entrypoint.call_count == 1
    implementation.module.read_package.assert_called_once_with()
    implementation.function.read_signature.assert_called_once_with()
    validate.assert_called_once_with(validation.CallableValidationContext(function, signature))
    assert plan.resources["signatures"] == {
        plan.invocations[0].id: "float",
        plan.invocations[1].id: "float",
    }


def test_compiler_logs_signature_validation_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=compiler.__name__)
    compiler.Compiler().compile(spec.Spec())
    assert any(
        message.startswith("  Signature checks for 0 functions:") for message in caplog.messages
    )


@pytest.mark.parametrize("features", [None, [], ["missing"], "result"])
def test_compiler_logs_feature_and_graph_checks_before_failure(
    caplog: pytest.LogCaptureFixture, features: list[str] | str | None
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely")
    builder = compiler.Compiler()
    specification = spec.Spec()
    caplog.clear()

    if features:
        with pytest.raises(ValueError):
            builder.compile(specification, features=features)
    else:
        builder.compile(specification, features=features)

    assert caplog.messages.count("\nCompiler validation:") == 1
    compiler_start = caplog.messages.index("\nCompiler validation:")
    assert caplog.messages[0] == "  Reference checks:"
    assert caplog.messages.index("    - checking globally unique profile IDs") < compiler_start
    assert caplog.messages[compiler_start : compiler_start + 3] == [
        "\nCompiler validation:",
        "  Feature selection:",
        "    - checking feature selection is a collection, not a string",
    ]
    if isinstance(features, str):
        assert len(caplog.messages) == compiler_start + 3
    elif features:
        assert caplog.messages[-1] == "    - checking selected output features have producers"
        assert "    - checking dependency graph is acyclic and schedulable" not in caplog.messages
    else:
        assert "  Invocation graph:" in caplog.messages
        assert "    - checking dependency graph is acyclic and schedulable" in caplog.messages
        assert "  Entrypoints:" in caplog.messages
        assert "  Package provenance:" in caplog.messages
        assert "  Execution plan:" in caplog.messages
        assert caplog.messages[-1] == (
            "    - checking emitted invocation IDs, dependencies, and stage ordering"
        )
        assert not any("Compiled plan:" in message for message in caplog.messages)
        caplog.clear()
        builder.compile(specification, features=features)
        assert caplog.messages.count("\nCompiler validation:") == 1
