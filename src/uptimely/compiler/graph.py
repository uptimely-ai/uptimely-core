"""Describe invocation dependencies and resolve execution order."""

from __future__ import annotations

import dataclasses
import logging

import graphable as graphable_

from uptimely import spec
from uptimely.spec import function_kinds as functions
from uptimely.spec import model as spec_model
from uptimely.spec import row_context

logger = logging.getLogger(__name__)

type GraphNode = graphable_.graphable.Graphable


@dataclasses.dataclass(frozen=True)
class InvocationNode:
    """One function invocation in the compilation graph."""

    function_id: str
    dataset_id: str
    operator_id: str
    function_kind: functions.FunctionKindId
    output_features: tuple[str, ...] = ()
    arguments: dict[str, spec_model.BindingArgument] = dataclasses.field(
        default_factory=dict, compare=False, hash=False
    )
    input_features: tuple[str, ...] = ()
    row_context: row_context.RowContext | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this invocation."""
        return (
            f"invocation:{self.function_kind}:{self.function_id}:"
            f"{self.dataset_id}:{self.operator_id}"
        )

    def __str__(self) -> str:
        return f"{self.function_kind}:{self.function_id}({self.dataset_id})"

    def __repr__(self) -> str:
        return f"{self.function_kind}:{self.function_id}({self.dataset_id})"


class InvocationGraph:
    """Dependency graph built from interface features and fragment merges."""

    def __init__(
        self, spec_definition: spec.Spec, *, graph: graphable_.graph.Graph | None = None
    ) -> None:
        """Build a dependency graph from a validated Spec.

        Args:
            spec_definition: The validated Spec containing operators and functions.
            graph: An existing graph to index, used when constructing a subset.
        """
        self.spec = spec_definition
        self.graph = self._create_graph() if graph is None else graph
        self._nodes = {node.reference.node_id: node for node in self.graph}
        self._feature_producers = self._index_feature_producers(self.invocations)

    def _create_graph(self) -> graphable_.graph.Graph:
        """Build invocation dependencies from operator interfaces and fragment merges."""
        nodes = self._create_nodes()
        graph = graphable_.graph.Graph(set(nodes.values()), discover=False)
        self._add_edges(graph, nodes)
        return graph

    def _create_nodes(self) -> dict[str, GraphNode]:
        """Create compute and optional merge nodes for each operator."""
        nodes: dict[str, GraphNode] = {}

        for key, operator in self.spec.operator_items:
            profile_id = key[0]
            profile = self.spec.profiles_by_key[profile_id]
            function_kind = self.spec.functions[operator.compute.function].kind
            function_definition = functions.FUNCTION_KINDS[function_kind]
            outputs = operator.output_features
            invocation = InvocationNode(
                function_id=operator.compute.function,
                dataset_id=profile.id,
                operator_id=operator.id,
                function_kind=function_kind,
                output_features=tuple(outputs),
                arguments=operator.compute.args,
                input_features=tuple(operator.input_features),
                row_context=operator.row_context,
            )
            nodes[invocation.node_id] = graphable_.graphable.Graphable(invocation)
            if function_definition.produces_fragment and operator.merge is not None:
                merge_kind = self.spec.functions[operator.merge.function].kind
                merge_invocation = InvocationNode(
                    function_id=operator.merge.function,
                    dataset_id=profile.id,
                    operator_id=operator.id,
                    function_kind=merge_kind,
                    arguments=operator.merge.args,
                )
                nodes[merge_invocation.node_id] = graphable_.graphable.Graphable(merge_invocation)
        return nodes

    def _add_edges(
        self,
        graph: graphable_.graph.Graph,
        nodes: dict[str, GraphNode],
    ) -> None:
        """Connect declared feature dependencies and compute-to-merge edges."""
        feature_producers = self._index_feature_producers(
            [node.reference for node in nodes.values()]
        )
        by_binding = {
            (node.dataset_id, node.operator_id, node.function_id): node
            for node in (graph_node.reference for graph_node in nodes.values())
        }
        for graph_node in nodes.values():
            invocation = graph_node.reference
            merge = self._merge_for(invocation, by_binding)
            if merge is not None:
                graph.add_edge(
                    graph_node,
                    nodes[merge.node_id],
                )
            for feature in invocation.input_features:
                producer = feature_producers.get(feature)
                if producer is not None and producer != invocation:
                    graph.add_edge(
                        nodes[producer.node_id],
                        graph_node,
                    )

    def _merge_for(
        self,
        node: InvocationNode,
        by_binding: dict[tuple[str, str, str], InvocationNode],
    ) -> InvocationNode | None:
        """Return the configured merge node for a fragment-producing invocation."""
        if not functions.FUNCTION_KINDS[node.function_kind].produces_fragment:
            return None
        merge = self.operator_for(node).merge
        if merge is None:
            return None
        return by_binding.get((node.dataset_id, node.operator_id, merge.function))

    def _index_feature_producers(
        self, invocations: list[InvocationNode]
    ) -> dict[str, InvocationNode]:
        """Map declared logical outputs to their producing invocations."""
        by_binding = {
            (node.dataset_id, node.operator_id, node.function_id): node for node in invocations
        }
        producers: dict[str, InvocationNode] = {}
        for compute in invocations:
            definition = functions.FUNCTION_KINDS[compute.function_kind]
            if not definition.produces_features:
                continue
            output = self._merge_for(compute, by_binding) or compute
            for feature in compute.output_features:
                producers[feature] = output
        return producers

    def profile_for(self, node: InvocationNode) -> spec.Profile:
        """Return a node's profile by its globally unique ID."""
        return self.spec.profiles[node.dataset_id]

    def operator_for(self, node: InvocationNode) -> spec.Operator:
        """Return the declaration that produced an invocation node."""
        return self.profile_for(node).assembly[node.operator_id]

    def topology(self) -> list[list[InvocationNode]]:
        """Return invocations grouped by dependency level (topological order)."""
        logger.debug("  Invocation graph:")
        logger.debug("    - checking dependency graph is acyclic and schedulable")
        levels = self.graph.parallelized_topological_order()
        return [[level_node.reference for level_node in level] for level in levels]

    def subset(self, features: list[str]) -> InvocationGraph:
        """Return the dependency closure needed to produce selected features."""
        logger.debug("    - checking selected output features have producers")
        selectable_features = self._feature_producers.keys() - self.spec.grain_key_ids
        missing = sorted(set(features) - selectable_features)
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        requested_nodes = [self._feature_producers[feature] for feature in features]

        selected_nodes = {self._node_by_key(node.node_id) for node in requested_nodes}
        for node in list(selected_nodes):
            selected_nodes.update(self.graph.ancestors(node))

        selected_dataset_ids = {node.dataset_id for node in requested_nodes}
        for invocation in self.invocations:
            function_kind = self.spec.functions[invocation.function_id].kind
            if not functions.FUNCTION_KINDS[function_kind].is_sink:
                continue
            if invocation.dataset_id not in selected_dataset_ids:
                continue
            sink_node = self._node_by_key(invocation.node_id)
            selected_nodes.add(sink_node)
            selected_nodes.update(self.graph.ancestors(sink_node))

        graph = graphable_.graph.Graph(selected_nodes, discover=False).clone(include_edges=True)
        return self.__class__(self.spec, graph=graph)

    def _node_by_key(self, node_key: str) -> GraphNode:
        """Return a graph node using an invocation node identifier."""
        try:
            return self._nodes[node_key]
        except KeyError as error:
            raise ValueError(f"Invocation node not found: {node_key}") from error

    @property
    def invocations(self) -> list[InvocationNode]:
        """All invocation nodes in the graph."""
        return [node.reference for node in self.graph]

    def dependencies(self, node: InvocationNode) -> list[InvocationNode]:
        """Return invocations that directly produce a node's dependencies."""
        graph_node = self._node_by_key(node.node_id)
        return sorted(
            (dependency.reference for dependency in graph_node.depends_on),
            key=lambda dependency: dependency.node_id,
        )

    def get_invocation_order(self) -> list[InvocationNode]:
        """Return invocation nodes in execution order (topological sort)."""
        return [node for level in self.topology() for node in level]
