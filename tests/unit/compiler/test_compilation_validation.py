"""Compiler orchestration ordering and fail-fast behavior."""

import logging
from unittest import mock

import pytest

from uptimely import plan as execution_plan
from uptimely import spec
from uptimely.codebase.python import entrypoint
from uptimely.compiler import compiler, validation
from uptimely.compiler import graph as invocation_graph
from uptimely.spec import model as spec_model


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "spec",
        "nodes",
        "graph",
        "selection",
        "topology",
        "invocation",
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
        returns="dataframe",
        entrypoint="module:calculate",
    )
    specification = spec.Spec(functions={"calculate": function})
    graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    selected_graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    node = invocation_graph.InvocationNode(
        function_id="calculate",
        profile_id="entity",
        operator_id="calculate",
        role="compute",
        result="target",
    )
    selected_graph.invocations = [node]
    selected_graph.dependencies.return_value = []
    emitted_invocation = execution_plan.Invocation(
        id=node.node_id,
        role="compute",
        result="target",
        entrypoint="module:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="entity",
        return_type="float",
        package=execution_plan.Package(distribution=None, version=None),
    )
    operations = {
        "spec": mock.Mock(),
        "nodes": mock.Mock(return_value=[node]),
        "graph": mock.Mock(return_value=(graph, {})),
        "selection": mock.Mock(return_value=selected_graph),
        "topology": mock.Mock(return_value=[[node]]),
        "entrypoint": mock.Mock(),
        "package": mock.Mock(return_value=entrypoint.PackageOrigin(None, None)),
        "signature": mock.Mock(return_value=entrypoint.Signature(return_annotation=float)),
        "signature_validation": mock.Mock(),
        "invocation": mock.Mock(return_value=emitted_invocation),
    }
    implementation = mock.Mock()
    implementation.read_package = operations["package"]
    implementation.read_signature = operations["signature"]
    operations["entrypoint"].return_value = implementation
    selected_graph.topology = operations["topology"]
    calls = mock.Mock()
    for name, step in operations.items():
        calls.attach_mock(step, name)
    if failure is not None:
        operations[failure].side_effect = ValueError("invalid compilation")

    monkeypatch.setattr(compiler.spec_validation, "validate_spec", operations["spec"])
    monkeypatch.setattr(compiler.Compiler, "_create_invocation_nodes", operations["nodes"])
    monkeypatch.setattr(compiler.Compiler, "_create_invocation_graph", operations["graph"])
    monkeypatch.setattr(compiler.Compiler, "_select_invocations", operations["selection"])
    monkeypatch.setattr(execution_plan.Invocation, "from_node", operations["invocation"])
    monkeypatch.setattr(compiler.entrypoint, "Entrypoint", operations["entrypoint"])
    monkeypatch.setattr(
        compiler.validation, "validation_callable_signature", operations["signature_validation"]
    )

    compiler_instance = compiler.Compiler()
    features = ["result", "result"]
    if failure is None:
        plan = compiler_instance.compile(specification, features=features)
    else:
        with pytest.raises(ValueError, match="invalid compilation"):
            compiler_instance.compile(specification, features=features)
    assert compiler_instance.__dict__ == {}

    expected = [
        mock.call.spec(specification),
        mock.call.nodes(specification),
        mock.call.graph(specification, [node]),
        mock.call.selection(specification, graph, [node], {}, ["result"]),
        mock.call.topology(),
        mock.call.entrypoint("module:calculate"),
        mock.call.package(),
        mock.call.signature(),
        mock.call.signature_validation(
            validation.CallableValidationContext(
                function, entrypoint.Signature(return_annotation=float)
            )
        ),
        mock.call.invocation(
            specification,
            node,
            dependency_ids=[],
            return_type="float",
            package=execution_plan.Package(distribution=None, version=None),
        ),
    ]
    if failure is not None:
        expected = expected[: list(operations).index(failure) + 1]
    assert calls.mock_calls == expected
    if failure is None:
        assert len(plan.invocations) == 1
        assert plan.invocations[0].id == emitted_invocation.id
        assert [stage.invocation_ids for stage in plan.stages] == [[node.node_id]]
        assert plan.invocations[0].return_type == "float"
        assert plan.invocations[0].package == execution_plan.Package(
            distribution=None,
            version=None,
        )
        assert calls.mock_calls == expected


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


def test_compiler_inspects_unique_functions_once_and_skips_disabled_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function = spec_model.FunctionTemplate(
        id="calculate",
        returns="dataframe",
        entrypoint="module:calculate",
    )
    disabled = function.model_copy(update={"id": "disabled", "validate_signature": False})
    specification = spec.Spec(functions={"calculate": function, "disabled": disabled})
    monkeypatch.setattr(compiler.spec_validation, "validate_spec", mock.Mock())
    signature = entrypoint.Signature(return_annotation=float)
    implementation = mock.Mock()
    implementation.read_package.return_value = entrypoint.PackageOrigin(None, None)
    implementation.read_signature.return_value = signature
    parse_entrypoint = mock.Mock(return_value=implementation)
    validate = mock.Mock()
    monkeypatch.setattr(compiler.entrypoint, "Entrypoint", parse_entrypoint)
    monkeypatch.setattr(compiler.validation, "validation_callable_signature", validate)
    nodes = [
        invocation_graph.InvocationNode(
            function_id=function_id,
            profile_id="entity",
            operator_id=operator,
            role="compute",
            result="target",
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
    graph.dependencies.return_value = []
    monkeypatch.setattr(
        compiler.Compiler, "_create_invocation_nodes", mock.Mock(return_value=nodes)
    )
    monkeypatch.setattr(
        compiler.Compiler, "_create_invocation_graph", mock.Mock(return_value=(graph, {}))
    )

    def create_invocation(
        _specification: spec.Spec,
        node: invocation_graph.InvocationNode,
        *,
        dependency_ids: list[str],
        return_type: str | None,
        package: execution_plan.Package,
    ) -> execution_plan.Invocation:
        return execution_plan.Invocation(
            id=node.node_id,
            role=node.role,
            result=node.result,
            entrypoint="module:calculate",
            function_id=node.function_id,
            operator_id=node.operator_id,
            profile_id=node.profile_id,
            dependency_ids=dependency_ids,
            return_type=return_type,
            package=package,
        )

    monkeypatch.setattr(
        execution_plan.Invocation,
        "from_node",
        mock.Mock(side_effect=create_invocation),
    )

    plan = compiler.Compiler().compile(specification)

    assert parse_entrypoint.call_count == 1
    implementation.read_package.assert_called_once_with()
    implementation.read_signature.assert_called_once_with()
    validate.assert_called_once_with(validation.CallableValidationContext(function, signature))
    assert [invocation.return_type for invocation in plan.invocations] == [
        "float",
        "float",
        None,
    ]


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
    monkeypatch.setattr(compiler.validation, "validation_callable_signature", validate)
    signatures = compiler.Compiler._validate_signatures(
        {"first": first, "second": second},
        {"module:calculate": implementation},
    )

    implementation.read_signature.assert_called_once_with()
    assert validate.call_args_list == [
        mock.call(validation.CallableValidationContext(first, signature)),
        mock.call(validation.CallableValidationContext(second, signature)),
    ]
    assert signatures == {"first": signature, "second": signature}


def test_compiler_logs_signature_validation_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=compiler.__name__)
    compiler.Compiler().compile(spec.Spec())
    assert (
        "Validate callable signatures for 0 functions; skip 0 disabled functions" in caplog.messages
    )


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
    assert caplog.messages.count(selection_check) == 1
    compiler_start = caplog.messages.index(selection_check)
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
        assert "Resolve package ownership for 0 unique entrypoints" in caplog.messages
        assert caplog.messages[-1] == (
            "Validate invocation IDs, dependencies, and execution stages"
        )
        assert not any("Compiled plan:" in message for message in caplog.messages)
        caplog.clear()
        compiler_instance.compile(specification, features=features)
        assert caplog.messages.count(selection_check) == 1
