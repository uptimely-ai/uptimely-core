"""Compiler orchestration ordering and fail-fast behavior."""

import logging
from unittest import mock

import pytest

from uptimely import plan as execution_plan
from uptimely import spec
from uptimely.codebase.python import entrypoint
from uptimely.compiler import compiler
from uptimely.compiler import graph as invocation_graph
from uptimely.inspector import bindings as inspector
from uptimely.spec import model as spec_model


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "spec",
        "create",
        "publishers",
        "dependencies",
        "graph",
        "selection",
        "topology",
        "invocation",
        "entrypoint",
        "package",
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
    node = invocation_graph.InvocationNode(node_id="calculate--1234567890")
    selected_graph.invocations = [node]
    selected_graph.dependencies.return_value = []
    emitted_invocation = execution_plan.Invocation(
        id=node.node_id,
        entrypoint="module:calculate",
        semantics=execution_plan.InvocationSemantics(
            role="compute",
            result="target",
            function_id="calculate",
            operator_id="calculate",
            profile_id="entity",
            return_type="float",
            package=execution_plan.Package(distribution=None, version=None),
        ),
    )
    semantics = execution_plan.InvocationSemantics(
        function_id="calculate",
        profile_id="entity",
        operator_id="calculate",
        role="compute",
        result="target",
    )
    operators = [
        compiler._OperatorInvocations(
            profile=spec_model.Profile(id="entity"),
            operator=spec_model.Operator(
                id="calculate", compute=spec_model.Binding(function="calculate")
            ),
            bindings={"compute": (node, semantics)},
        )
    ]
    publishers = compiler._Publishers(features={}, datasets={}, seeds={})
    operations = {
        "spec": mock.Mock(),
        "create": mock.Mock(return_value=operators),
        "publishers": mock.Mock(return_value=publishers),
        "dependencies": mock.Mock(return_value={node.node_id: set()}),
        "graph": mock.Mock(return_value=graph),
        "selection": mock.Mock(return_value={node.node_id}),
        "topology": mock.Mock(return_value=[[node]]),
        "entrypoint": mock.Mock(),
        "package": mock.Mock(return_value=entrypoint.PackageOrigin(None, None)),
        "invocation": mock.Mock(return_value=emitted_invocation),
    }
    implementation = mock.Mock()
    implementation.read_package = operations["package"]
    operations["entrypoint"].return_value = implementation
    selected_graph.topology = operations["topology"]
    graph.ancestors.return_value = set()
    graph.subset.return_value = selected_graph
    calls = mock.Mock()
    for name, step in operations.items():
        calls.attach_mock(step, name)
    if failure is not None:
        operations[failure].side_effect = ValueError("invalid compilation")

    monkeypatch.setattr(compiler.spec_validation, "validate_spec", operations["spec"])
    monkeypatch.setattr(compiler.Compiler, "_create_invocations", operations["create"])
    monkeypatch.setattr(compiler.Compiler, "_index_publishers", operations["publishers"])
    monkeypatch.setattr(compiler.Compiler, "_resolve_dependencies", operations["dependencies"])
    monkeypatch.setattr(compiler.Compiler, "_select_invocations", operations["selection"])
    monkeypatch.setattr(compiler.invocation_graph, "InvocationGraph", operations["graph"])
    monkeypatch.setattr(execution_plan.Invocation, "from_node", operations["invocation"])
    monkeypatch.setattr(compiler.entrypoint, "Entrypoint", operations["entrypoint"])
    compiler_instance = compiler.Compiler()
    features = ["result", "result"]
    if failure is None:
        plan = compiler_instance.compile(
            specification,
            features=features,
            signatures={"calculate": entrypoint.Signature(return_annotation=float)},
        )
    else:
        with pytest.raises(ValueError, match="invalid compilation"):
            compiler_instance.compile(
                specification,
                features=features,
                signatures={"calculate": entrypoint.Signature(return_annotation=float)},
            )
    assert compiler_instance.__dict__ == {}

    expected = [
        mock.call.spec(specification),
        mock.call.create(specification),
        mock.call.publishers(operators),
        mock.call.dependencies(specification, operators, publishers),
        mock.call.graph([node], {node.node_id: set()}),
        mock.call.selection(specification, {node.node_id: semantics}, {}, ["result", "result"]),
        mock.call.topology(),
        mock.call.entrypoint("module:calculate"),
        mock.call.package(),
        mock.call.invocation(
            specification,
            node,
            dependency_ids=[],
            return_type="float",
            package=execution_plan.Package(distribution=None, version=None),
            semantics=semantics,
        ),
    ]
    if failure is not None:
        expected = expected[: list(operations).index(failure) + 1]
    assert calls.mock_calls == expected
    if failure is None:
        assert len(plan.invocations) == 1
        assert plan.invocations[0].id == emitted_invocation.id
        assert [stage.invocation_ids for stage in plan.stages] == [[node.node_id]]
        assert plan.invocations[0].semantics.return_type == "float"
        assert plan.invocations[0].semantics.package == execution_plan.Package(
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
    monkeypatch.setattr(inspector.BindingInspection, "inspect", validate)
    calls = [("calculate", "first"), ("calculate", "second"), ("disabled", "third")]
    nodes = [invocation_graph.InvocationNode(node_id=operator) for _, operator in calls]
    graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    graph.topology.return_value = [nodes]
    graph.invocations = nodes
    graph.dependencies.return_value = []
    operators = [
        compiler._OperatorInvocations(
            profile=spec_model.Profile(id="entity"),
            operator=spec_model.Operator(
                id=operator, compute=spec_model.Binding(function=function_id)
            ),
            bindings={
                "compute": (
                    node,
                    execution_plan.InvocationSemantics(
                        function_id=function_id,
                        profile_id="entity",
                        operator_id=operator,
                        role="compute",
                        result="target",
                    ),
                )
            },
        )
        for node, (function_id, operator) in zip(nodes, calls, strict=True)
    ]
    monkeypatch.setattr(compiler.Compiler, "_create_invocations", mock.Mock(return_value=operators))
    monkeypatch.setattr(
        compiler.Compiler,
        "_resolve_dependencies",
        mock.Mock(return_value={node.node_id: set() for node in nodes}),
    )
    monkeypatch.setattr(compiler.invocation_graph, "InvocationGraph", mock.Mock(return_value=graph))

    def create_invocation(
        _specification: spec.Spec,
        node: invocation_graph.InvocationNode,
        *,
        dependency_ids: list[str],
        return_type: str | None,
        package: execution_plan.Package,
        semantics: execution_plan.InvocationSemantics,
    ) -> execution_plan.Invocation:
        return execution_plan.Invocation(
            id=node.node_id,
            entrypoint="module:calculate",
            semantics=semantics.__replace__(
                dependency_ids=dependency_ids,
                return_type=return_type,
                package=package,
            ),
        )

    monkeypatch.setattr(
        execution_plan.Invocation,
        "from_node",
        mock.Mock(side_effect=create_invocation),
    )

    plan = compiler.Compiler().compile(
        specification,
        signatures={"calculate": signature},
    )

    assert parse_entrypoint.call_count == 1
    implementation.read_package.assert_called_once_with()
    assert [invocation.semantics.return_type for invocation in plan.invocations] == [
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
        assert "Resolve package ownership for 0 unique entrypoints" in caplog.messages
        assert caplog.messages[-1] == (
            "Validate invocation IDs, dependencies, and execution stages"
        )
        assert not any("Compiled plan:" in message for message in caplog.messages)
        caplog.clear()
        compiler_instance.compile(specification, features=features)
        assert caplog.messages.count(selection_check) == 0
