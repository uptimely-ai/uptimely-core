"""Compact invocation identity and collision handling."""

import hashlib
import re

import pytest

from uptimely import plan, spec
from uptimely.compiler import compiler, graph
from uptimely.spec import model as spec_model


def _invocation_id(
    operator_id: str = "bearing_temperature_delta",
    *,
    function_id: str = "delta",
    profile_id: str = "pump_telemetry",
    role: spec_model.profile.OperatorBindingRole.Value = "compute",
) -> str:
    return graph.InvocationNode.create_id(
        function_id=function_id,
        profile_id=profile_id,
        operator_id=operator_id,
        role=role,
    )


def test_invocation_id_uses_operator_label_and_canonical_fingerprint() -> None:
    invocation_id = _invocation_id()
    identity = b'["delta","pump_telemetry","bearing_temperature_delta","compute"]'
    fingerprint = hashlib.sha256(identity).hexdigest()[:10]

    assert invocation_id == f"bearing-temperature-delt--{fingerprint}"
    assert _invocation_id() == invocation_id


@pytest.mark.parametrize(
    ("operator_id", "label"),
    [
        ("Read__PUMP---Telemetry", "read-pump-telemetry"),
        ("  first / second:third  ", "first-second-third"),
        ("a" * 100, "a" * 24),
        ("a" * 23 + "_remaining", "a" * 23),
        ("___", "invocation"),
        ("\u6e29\u5ea6", "invocation"),
    ],
)
def test_invocation_labels_are_bounded_ascii_with_single_dashes(
    operator_id: str, label: str
) -> None:
    identifier = _invocation_id(operator_id)

    assert identifier.split("--")[0] == label
    assert len(identifier) <= 36
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{10}", identifier)


def test_compute_and_merge_roles_have_distinct_invocation_ids() -> None:
    compute = _invocation_id()
    merge = _invocation_id(role="merge")

    assert merge.split("--")[0] == compute.split("--")[0]
    assert len(merge) <= 36
    assert merge != compute


@pytest.mark.parametrize(
    "changes",
    [
        {"function_id": "another_delta"},
        {"profile_id": "another_profile"},
        {"operator_id": "bearing-temperature-delta"},
        {"operator_id": "bearing_temperature_delta_extra"},
    ],
)
def test_fingerprint_distinguishes_each_identity_field(changes: dict[str, str]) -> None:
    original = _invocation_id()
    changed = _invocation_id(**changes)

    assert changed.rsplit("--", 1)[1] != original.rsplit("--", 1)[1]


def test_identity_serialization_preserves_field_boundaries() -> None:
    first = _invocation_id(
        function_id="delta:pump",
        profile_id="telemetry",
    )
    second = _invocation_id(
        function_id="delta",
        profile_id="pump:telemetry",
    )

    assert first != second


def test_graph_orders_and_selects_nodes_with_semantics() -> None:
    first, second, third = (
        graph.InvocationNode(
            node_id=name,
            semantics=plan.InvocationSemantics(
                function_id=name,
                profile_id="data",
                operator_id=name,
                role="compute",
                result="none",
                input_features=["input"],
            ),
        )
        for name in ("first", "second", "third")
    )
    invocation_graph = graph.InvocationGraph(
        [first, second, third],
        {"first": set(), "second": {"first"}, "third": {"second"}},
    )

    assert invocation_graph.topology() == [[first], [second], [third]]
    assert invocation_graph.ancestors("third") == {first, second}
    assert invocation_graph.dependencies(third) == [second]
    assert invocation_graph.subset(["first", "second"]).topology() == [[first], [second]]
    ancestor = next(node for node in invocation_graph.ancestors("third") if node.node_id == "first")
    assert ancestor.semantics is first.semantics


def test_node_identity_does_not_depend_on_semantics() -> None:
    semantics = plan.InvocationSemantics(
        function_id="first",
        profile_id="data",
        operator_id="first",
        role="compute",
        result="none",
        input_features=["input"],
    )
    first = graph.InvocationNode("same", semantics)
    other = graph.InvocationNode("same", semantics.__replace__(input_features=["other"]))
    assert first == other
    assert len({first, other}) == 1


def test_graph_rejects_id_collisions_before_overwriting_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = spec.Spec(
        functions={
            "delta": spec_model.FunctionTemplate(
                id="delta",
                returns="dataframe",
                entrypoint="support.functions:vectorize",
            )
        },
        profiles={
            "data": spec_model.Profile(
                id="data",
                assembly={
                    name: spec_model.Operator(id=name, compute=spec_model.Binding(function="delta"))
                    for name in ("first", "second")
                },
            )
        },
    )
    monkeypatch.setattr(graph.InvocationNode, "create_id", lambda *args: "same--0000000000")

    with pytest.raises(ValueError, match=r"Invocation ID collision.*first.*second"):
        compiler.Compiler().compile(specification, validate_spec=False)
