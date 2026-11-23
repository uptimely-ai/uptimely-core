"""Generic dependency ordering for compiler-created invocation nodes."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Collection

import graphable as graphable_

type GraphNode = graphable_.graphable.Graphable

INVOCATION_LABEL_MAX_LENGTH = 24
INVOCATION_HASH_LENGTH = 10


@dataclasses.dataclass(frozen=True)
class InvocationNode:
    """Graph node identified by an opaque invocation ID."""

    node_id: str

    @staticmethod
    def create_id(function_id: str, profile_id: str, operator_id: str, role: str) -> str:
        """Create a stable graph ID from the source call identity.

        Args:
            function_id: Bound function identifier.
            profile_id: Profile containing the operator.
            operator_id: Operator identifier.
            role: Binding role within the operator.

        Returns:
            A deterministic opaque invocation ID.
        """
        identity = json.dumps((function_id, profile_id, operator_id, role), separators=(",", ":"))
        fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:INVOCATION_HASH_LENGTH]
        label = re.sub(r"[^a-z0-9]+", "-", operator_id.lower()).strip("-") or "invocation"
        label = label[:INVOCATION_LABEL_MAX_LENGTH].rstrip("-")
        return f"{label}--{fingerprint}"


class InvocationGraph:
    """Generic dependency graph for nodes and dependencies supplied by the compiler."""

    def __init__(
        self,
        invocations: Collection[InvocationNode],
        dependencies: dict[str, Collection[str]],
    ) -> None:
        """Build an execution graph from nodes and their dependency identifiers.

        Args:
            invocations: Nodes already created by the compiler.
            dependencies: Invocation identifiers mapped to their prerequisites.
        """
        invocation_order = list(invocations)
        nodes_by_id: dict[str, GraphNode] = {}
        for invocation in invocation_order:
            if invocation.node_id in nodes_by_id:
                raise ValueError(f"Duplicate invocation node ID: {invocation.node_id}")
            nodes_by_id[invocation.node_id] = graphable_.graphable.Graphable(invocation)
        self.graph = graphable_.graph.Graph(
            set(nodes_by_id.values()),
            discover=False,
        )
        self._nodes = nodes_by_id
        self._invocations = invocation_order
        for invocation_id, dependency_ids in dependencies.items():
            invocation = self._node_by_key(invocation_id)
            for dependency_id in dependency_ids:
                self.graph.add_edge(self._node_by_key(dependency_id), invocation)

    @classmethod
    def _from_graph(
        cls,
        graph: graphable_.graph.Graph,
        invocations: list[InvocationNode],
    ) -> InvocationGraph:
        """Wrap an induced subgraph without interpreting its nodes or edges."""
        instance = cls.__new__(cls)
        instance.graph = graph
        instance._nodes = {node.reference.node_id: node for node in graph}
        instance._invocations = invocations
        return instance

    def topology(self) -> list[list[InvocationNode]]:
        """Return nodes grouped by dependency level in topological order."""
        levels = self.graph.parallelized_topological_order()
        order = {invocation.node_id: index for index, invocation in enumerate(self._invocations)}
        return [
            sorted((node.reference for node in level), key=lambda node: order[node.node_id])
            for level in levels
        ]

    def ancestors(self, invocation_id: str) -> set[InvocationNode]:
        """Return all prerequisite nodes of an invocation."""
        return {node.reference for node in self.graph.ancestors(self._node_by_key(invocation_id))}

    def subset(self, invocation_ids: Collection[str]) -> InvocationGraph:
        """Return the induced subgraph containing the supplied node identifiers."""
        selected_ids = set(invocation_ids)
        selected_nodes = {self._node_by_key(node_id) for node_id in selected_ids}
        graph = graphable_.graph.Graph(selected_nodes, discover=False).clone(include_edges=True)
        invocations = [
            invocation for invocation in self._invocations if invocation.node_id in selected_ids
        ]
        return self._from_graph(graph, invocations)

    def _node_by_key(self, node_key: str) -> GraphNode:
        """Return a graph node using an invocation node identifier."""
        try:
            return self._nodes[node_key]
        except KeyError as error:
            raise ValueError(f"Invocation node not found: {node_key}") from error

    @property
    def invocations(self) -> list[InvocationNode]:
        """All invocation nodes in the graph."""
        return list(self._invocations)

    def dependencies(self, node: InvocationNode) -> list[InvocationNode]:
        """Return nodes that directly precede the given invocation."""
        graph_node = self._node_by_key(node.node_id)
        return sorted(
            (dependency.reference for dependency in graph_node.depends_on),
            key=lambda dependency: dependency.node_id,
        )

    def get_invocation_order(self) -> list[InvocationNode]:
        """Return invocation nodes in execution order (topological sort)."""
        return [node for level in self.topology() for node in level]
