"""Compiler orchestration ordering and fail-fast behavior."""

import functools
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

    def entrypoints(builder: compiler._Compilation) -> dict[str, object]:
        return operations["entrypoints"](
            [invocation.entrypoint for invocation in builder.invocations]
        )

    def packages(builder: compiler._Compilation) -> dict[str, object]:
        return operations["packages"](builder.entrypoints)

    def signatures(builder: compiler._Compilation) -> dict[str, object]:
        _ = builder.packages
        return operations["signatures"](builder.spec_definition, builder.graph, builder.entrypoints)

    for reader in (entrypoints, packages, signatures):
        descriptor = functools.cached_property(reader)
        descriptor.__set_name__(compiler._Compilation, reader.__name__)
        monkeypatch.setattr(compiler._Compilation, reader.__name__, descriptor)

    compilations: list[compiler._Compilation] = []
    original_init = compiler._Compilation.__init__

    def initialize(
        compilation: compiler._Compilation,
        spec_definition: spec.Spec,
        features: list[str] | None = None,
    ) -> None:
        original_init(compilation, spec_definition, features)
        compilations.append(compilation)

    monkeypatch.setattr(compiler._Compilation, "__init__", initialize)

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
    assert builder.__dict__ == {}
    if failure != "spec":
        assert compilations[0].features is features

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
        compilation = compilations[0]
        assert compilation.resources == plan.resources
        assert compilation.invocations == plan.invocations
        assert compilation.stages == plan.stages
        assert compilation.signature_resources == plan.resources["signatures"]
        assert compilation.entrypoint_packages is plan.resources["entrypoint_packages"]
        assert calls.mock_calls == expected
    else:
        operations[failure].side_effect = None
    calls.reset_mock()
    replacement = spec.Spec(name="second")
    builder.compile(replacement, features=["different"])
    latest = compilations[-1]
    assert latest.spec_definition is replacement
    assert latest.signature_resources is latest.resources["signatures"]
    assert latest.entrypoint_packages is latest.resources["entrypoint_packages"]
    if len(compilations) == 2:
        assert latest is not compilations[0]
        assert compilations[0].spec_definition is specification
    assert calls.mock_calls == [
        mock.call.spec(replacement),
        mock.call.graph(replacement),
        mock.call.subset(["different"]),
        mock.call.topology(),
        mock.call.entrypoints([]),
        mock.call.packages({}),
        mock.call.signatures(replacement, selected_graph, {}),
    ]


def test_compiler_has_no_active_build_properties() -> None:
    builder = compiler.Compiler()
    assert builder.__dict__ == {}
    assert not hasattr(builder, "graph")
    assert not hasattr(builder, "spec_definition")


@pytest.mark.parametrize("features", [None, [], (), set()])
def test_compilation_retains_feature_collection(
    features: list[str] | tuple[str, ...] | set[str] | None,
) -> None:
    builder = compiler._Compilation(spec.Spec(), features=features)
    builder.build_plan()
    assert builder.features is features


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


def test_nested_compilations_on_one_compiler_do_not_share_build_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = compiler.Compiler()
    outer_spec = spec.Spec(name="outer")
    inner_spec = spec.Spec(name="inner")
    original_build = compiler._Compilation.build_plan
    builds: list[compiler._Compilation] = []

    def build(compilation: compiler._Compilation) -> execution_plan.ExecutionPlan:
        builds.append(compilation)
        if compilation.spec_definition is outer_spec:
            outer_graph = compilation.graph
            inner_plan = builder.compile(inner_spec, features=[])
            assert inner_plan.invocations == []
            assert compilation.graph is outer_graph
            assert compilation.spec_definition is outer_spec
            assert compilation.features is None
        return original_build(compilation)

    monkeypatch.setattr(compiler._Compilation, "build_plan", build)
    outer_plan = builder.compile(outer_spec)

    assert outer_plan.invocations == []
    assert len(builds) == 2
    assert builds[0] is not builds[1]
    assert builds[0].graph is not builds[1].graph
    assert builds[0].resources is not builds[1].resources
    assert builder.__dict__ == {}


def test_signatures_reuse_function_contracts_only_within_one_compilation(
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
        invocation_graph.InvocationNode(
            function_id=function_id,
            dataset_id="entity",
            operator_id=operator,
            function_kind=specification.functions[function_id].kind,
        )
        for function_id, operator in [
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
    builder = compiler._Compilation(specification)
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

    replacement = compiler._Compilation(spec.Spec())
    assert replacement.function_signatures == {}
    assert replacement.signatures == {}


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
