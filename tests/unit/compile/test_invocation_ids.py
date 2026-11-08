"""Compact invocation identity and collision handling."""

import dataclasses
import hashlib
import re
from unittest import mock

import pytest

from uptimely import spec
from uptimely.compiler import graph
from uptimely.spec import model as spec_model


def _node(operator_id: str = "bearing_temperature_delta") -> graph.InvocationNode:
    return graph.InvocationNode(
        function_id="delta",
        profile_id="pump_telemetry",
        operator_id=operator_id,
        function_kind="vectorize",
    )


def test_invocation_id_uses_operator_label_and_canonical_fingerprint() -> None:
    node = _node()
    identity = b'["delta","pump_telemetry","bearing_temperature_delta"]'
    fingerprint = hashlib.sha256(identity).hexdigest()[:10]

    assert node.node_id == f"bearing-temperature-delt--{fingerprint}"
    assert dataclasses.replace(node).node_id == node.node_id


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
    identifier = _node(operator_id).node_id

    assert identifier.split("--")[0] == label
    assert len(identifier) <= 36
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{10}", identifier)


def test_compute_and_merge_share_label_but_have_distinct_function_fingerprints() -> None:
    compute = _node()
    merge = dataclasses.replace(
        compute, function_kind="merge", function_id="__uptimely_merge_by_grain"
    )

    assert merge.node_id.split("--")[0] == compute.node_id.split("--")[0]
    assert len(merge.node_id) <= 36
    assert merge.node_id != compute.node_id


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
    node = _node()
    changed = dataclasses.replace(node, **changes)

    assert changed.node_id.rsplit("--", 1)[1] != node.node_id.rsplit("--", 1)[1]


def test_identity_serialization_preserves_field_boundaries() -> None:
    first = dataclasses.replace(_node(), function_id="delta:pump", profile_id="telemetry")
    second = dataclasses.replace(_node(), function_id="delta", profile_id="pump:telemetry")

    assert first.node_id != second.node_id


def test_invocation_id_does_not_depend_on_runtime_metadata() -> None:
    node = _node()
    changed = dataclasses.replace(
        node,
        input_features=("input",),
        output_features=("output",),
        arguments={"value": spec_model.BindingArgument(42)},
    )

    assert changed.node_id == node.node_id


@pytest.mark.parametrize("kind", ["read", "vectorize", "merge", "escape"])
def test_invocation_id_does_not_depend_on_function_kind(kind: str) -> None:
    node = _node()

    assert dataclasses.replace(node, function_kind=kind).node_id == node.node_id


def test_graph_rejects_id_collisions_before_overwriting_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = spec.Spec(
        functions={
            "delta": spec_model.FunctionTemplate(
                id="delta",
                kind="vectorize",
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
    monkeypatch.setattr(
        graph.InvocationNode, "node_id", mock.PropertyMock(return_value="same--0000000000")
    )

    with pytest.raises(ValueError, match=r"Invocation ID collision.*first.*second"):
        graph.InvocationGraph(specification)
