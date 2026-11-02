"""Compiler orchestration ordering and fail-fast behavior."""

import functools
import logging
from unittest import mock

import pytest

from uptimely import entrypoint, spec
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
        "entrypoints",
        "packages",
        "signatures",
    ],
)
def test_compilation_passes_explicit_arguments_in_fail_fast_order(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    specification = spec.Spec()
    graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    selected_graph = mock.Mock(spec=invocation_graph.InvocationGraph)
    graph.subset.return_value = selected_graph
    selected_graph.topology.return_value = []
    operations = {
        "spec": mock.Mock(),
        "graph": mock.Mock(return_value=graph),
        "subset": graph.subset,
        "topology": selected_graph.topology,
        "entrypoints": mock.Mock(return_value={}),
        "packages": mock.Mock(return_value={}),
        "signatures": mock.Mock(return_value={}),
    }
    selected_graph.invocations = []
    calls = mock.Mock()
    for name, operation in operations.items():
        calls.attach_mock(operation, name)
    if failure is not None:
        operations[failure].side_effect = ValueError("invalid compilation")

    monkeypatch.setattr(compiler.spec_validation, "validate_spec", operations["spec"])
    monkeypatch.setattr(invocation_graph, "InvocationGraph", operations["graph"])

    def entrypoints(builder: compiler.Compiler) -> dict[str, object]:
        return operations["entrypoints"](
            [invocation.entrypoint for invocation in builder.invocations]
        )

    def packages(builder: compiler.Compiler) -> dict[str, object]:
        return operations["packages"](builder.entrypoints)

    def signatures(builder: compiler.Compiler) -> dict[str, object]:
        _ = builder.packages
        return operations["signatures"](builder.spec_definition, builder.graph, builder.entrypoints)

    for reader in (entrypoints, packages, signatures):
        descriptor = functools.cached_property(reader)
        descriptor.__set_name__(compiler.Compiler, reader.__name__)
        monkeypatch.setattr(compiler.Compiler, reader.__name__, descriptor)

    builder = compiler.Compiler()
    features = ["result", "result"]
    if failure is None:
        plan = builder.compile(specification, features=features)
        assert plan.invocations == []
        assert plan.stages == []
        assert plan.resources == {"signatures": {}, "entrypoint_packages": {}}
    else:
        with pytest.raises(ValueError, match="invalid compilation"):
            builder.compile(specification, features=features)
    assert builder.features is features

    expected = [
        mock.call.spec(specification),
        mock.call.graph(specification),
        mock.call.subset(["result"]),
        mock.call.topology(),
        mock.call.entrypoints([]),
        mock.call.packages({}),
        mock.call.signatures(specification, selected_graph, {}),
    ]
    if failure is not None:
        expected = expected[: list(operations).index(failure) + 1]
    assert calls.mock_calls == expected
    if failure is None:
        assert builder.resources is plan.resources
        assert builder.invocations is plan.invocations
        assert builder.stages is plan.stages
        assert builder.signature_resources is plan.resources["signatures"]
        assert builder.entrypoint_packages is plan.resources["entrypoint_packages"]
        assert calls.mock_calls == expected
    else:
        operations[failure].side_effect = None
    calls.reset_mock()
    replacement = spec.Spec(name="second")
    builder.compile(replacement, features=["different"])
    assert builder.signature_resources is builder.resources["signatures"]
    assert builder.entrypoint_packages is builder.resources["entrypoint_packages"]
    assert calls.mock_calls == [
        mock.call.spec(replacement),
        mock.call.graph(replacement),
        mock.call.subset(["different"]),
        mock.call.topology(),
        mock.call.entrypoints([]),
        mock.call.packages({}),
        mock.call.signatures(replacement, selected_graph, {}),
    ]


def test_compiler_build_properties_require_a_specification() -> None:
    with pytest.raises(RuntimeError, match="Call compile"):
        _ = compiler.Compiler().graph


@pytest.mark.parametrize("features", [None, [], (), set()])
def test_compiler_retains_feature_collection(
    features: list[str] | tuple[str, ...] | set[str] | None,
) -> None:
    builder = compiler.Compiler()
    builder.compile(spec.Spec(), features=features)
    assert builder.features is features


def test_compiler_rejects_string_features_and_recovers() -> None:
    builder = compiler.Compiler()
    specification = spec.Spec()
    original_plan = builder.compile(specification)

    with pytest.raises(ValueError, match="features must be a collection"):
        builder.compile(specification, features="result")
    with pytest.raises(RuntimeError, match="Call compile"):
        _ = builder.graph

    replacement_plan = builder.compile(specification, features=[])
    assert replacement_plan == original_plan
    assert replacement_plan.resources is not original_plan.resources
    assert builder.features == []


def test_signatures_reuse_function_contracts_and_reset_on_compile(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=compiler.__name__)
    function = spec_model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns="dataframe",
        entrypoint="missing_module:calculate",
    )
    disabled = function.model_copy(update={"id": "disabled", "validate_signature": False})
    specification = spec.Spec(functions={"calculate": function, "disabled": disabled})
    nodes = [
        invocation_graph.InvocationNode(function_id, "entity", "dataset", action)
        for function_id, action in [
            ("calculate", "first"),
            ("calculate", "second"),
            ("disabled", "third"),
        ]
    ]
    signature = mock.Mock(spec=entrypoint.Signature)
    implementation = mock.Mock(spec=entrypoint.Entrypoint)
    implementation.function.signature = signature
    validate = mock.Mock()
    monkeypatch.setattr(validation, "validation_callable_signature", validate)
    builder = compiler.Compiler()
    builder._spec_definition = specification
    builder.__dict__.update(
        graph=mock.Mock(invocations=nodes),
        entrypoints={function.entrypoint: implementation},
        packages={},
    )

    assert builder.function_signatures == {"calculate": signature}
    assert builder.signatures == {node.node_id: signature for node in nodes[:2]}
    validate.assert_called_once_with(validation.CallableValidationContext(function, signature))
    assert builder.signatures[nodes[0].node_id] is builder.signatures[nodes[1].node_id]
    assert caplog.messages == [
        "  Signature checks for 1 functions:\n"
        "    - checking callable signatures\n"
        "    - checking implementations accept declared arguments\n"
        "    - checking declared arguments can be passed as keywords\n"
        "    - checking declared implementation argument annotations\n"
        "    - checking required implementation parameters are declared\n"
        "    - checking declared implementation return annotations",
        "    - skipping 1 functions (validate_signature=false)",
    ]

    builder.compile(spec.Spec())
    assert builder.function_signatures == {}
    assert builder.signatures == {}


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
    assert caplog.messages[0] == "  Semantic checks:"
    assert caplog.messages.index("    - checking globally unique dataset IDs") < compiler_start
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
