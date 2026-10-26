"""Describe invocation dependencies and resolve execution order."""

from __future__ import annotations

import dataclasses

import graphable as graphable_

from uptimely import row_context, spec
from uptimely.spec import operations

from ..spec import binding_resolution
from ..spec import references as bindings

type GraphNode = graphable_.graphable.Graphable


@dataclasses.dataclass(frozen=True)
class InvocationNode:
    """One fragment, calculation, or sink function invocation."""

    function_id: str
    entity_id: str
    dataset_id: str
    mapping_id: str
    feature_id: str | None = None
    operation: operations.FunctionOperation = operations.VECTORIZE
    output_features: tuple[str, ...] = ()
    arguments: dict[str, object] = dataclasses.field(
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
            f"invocation:{self.operation}:{self.function_id}:"
            f"{self.entity_id}:{self.dataset_id}:{self.mapping_id}"
        )

    def __str__(self) -> str:
        return f"{self.function_id}({self.entity_id})"

    def __repr__(self) -> str:
        return f"{self.function_id}({self.entity_id})"


class InvocationGraph:
    """Dependency graph built from invocation nodes and their feature dependencies."""

    def __init__(
        self, spec_definition: spec.Spec, *, graph: graphable_.graph.Graph | None = None
    ) -> None:
        """Build a dependency graph from a validated Spec.

        Args:
            spec_definition: The validated Spec containing mappings and functions.
            graph: An existing graph to index, used when constructing a subset.
        """
        self.spec = spec_definition
        self.graph = self._create_graph() if graph is None else graph
        self._nodes = {node.reference.node_id: node for node in self.graph}

    def _create_graph(self) -> graphable_.graph.Graph:
        """Build graph nodes and connect their mapping, feature, and write dependencies."""
        nodes: dict[str, GraphNode] = {}
        feature_producers: dict[str, InvocationNode] = {}
        dataset_sources: dict[str, list[InvocationNode]] = {}
        dataset_sinks: dict[str, list[InvocationNode]] = {}
        calculations: dict[str, list[InvocationNode]] = {}

        for entity_id, entity in self.spec.entities.items():
            for dataset in entity.datasets.values():
                for mapping in dataset.mappings.values():
                    operation = bindings.mapping_operation(mapping, self.spec.functions)
                    feature_id = (
                        next(
                            (
                                feature
                                for feature in mapping.output_features
                                if feature not in entity.dimension_ids
                            ),
                            None,
                        )
                        if operation == operations.COLLAPSE
                        else mapping.output_features[0]
                        if mapping.output_features
                        else None
                    )
                    invocation = InvocationNode(
                        function_id=mapping.binding.function,
                        entity_id=entity_id,
                        dataset_id=dataset.id,
                        mapping_id=mapping.id,
                        feature_id=feature_id,
                        operation=operation,
                        output_features=tuple(mapping.output_features),
                        arguments=mapping.binding.args,
                        input_features=tuple(mapping.input_features),
                        row_context=mapping.row_context,
                    )
                    nodes[invocation.node_id] = graphable_.graphable.Graphable(invocation)
                    if operation == operations.WRITE:
                        dataset_sinks.setdefault(dataset.id, []).append(invocation)
                    elif operation in operations.FRAGMENT_OPERATIONS:
                        dataset_sources.setdefault(dataset.id, []).append(invocation)
                    elif operation == operations.VECTORIZE:
                        calculations.setdefault(dataset.id, []).append(invocation)
                    for feature in mapping.output_features:
                        if feature not in self.spec.dimensions:
                            feature_producers[feature] = invocation

        graph = graphable_.graph.Graph(set(nodes.values()), discover=False)
        self._add_source_dependencies(graph, nodes, dataset_sources)
        self._add_mapping_dependencies(
            graph, nodes, feature_producers, dataset_sources, calculations
        )
        self._add_calculation_dependencies(graph, nodes, dataset_sources, calculations)
        self._add_write_dependencies(graph, nodes, dataset_sources, dataset_sinks, calculations)
        return graph

    @staticmethod
    def _add_source_dependencies(
        graph: graphable_.graph.Graph,
        nodes: dict[str, GraphNode],
        dataset_sources: dict[str, list[InvocationNode]],
    ) -> None:
        """Make source transforms depend on reads in their dataset."""
        for fragments in dataset_sources.values():
            reads = [fragment for fragment in fragments if fragment.operation == operations.READ]
            downstream = [
                fragment for fragment in fragments if fragment.operation != operations.READ
            ]
            for fragment in downstream:
                for read in reads:
                    graph.add_edge(nodes[read.node_id], nodes[fragment.node_id])

    def _add_mapping_dependencies(
        self,
        graph: graphable_.graph.Graph,
        nodes: dict[str, GraphNode],
        feature_producers: dict[str, InvocationNode],
        dataset_sources: dict[str, list[InvocationNode]],
        calculations: dict[str, list[InvocationNode]],
    ) -> None:
        """Connect mapping dataframe and feature references to their producers."""
        for invocation in (node.reference for node in nodes.values()):
            dataset_references = binding_resolution.dataset_dependencies(
                invocation.arguments, invocation.dataset_id
            )
            for referenced_id in dataset_references:
                for source in dataset_sources.get(referenced_id, []):
                    if source != invocation and (
                        referenced_id != invocation.dataset_id
                        or source.operation == operations.READ
                    ):
                        graph.add_edge(nodes[source.node_id], nodes[invocation.node_id])

            for feature in invocation.input_features:
                producer = feature_producers.get(feature)
                if producer is not None and producer != invocation:
                    graph.add_edge(nodes[producer.node_id], nodes[invocation.node_id])

    @staticmethod
    def _add_calculation_dependencies(
        graph: graphable_.graph.Graph,
        nodes: dict[str, GraphNode],
        dataset_sources: dict[str, list[InvocationNode]],
        calculations: dict[str, list[InvocationNode]],
    ) -> None:
        """Make vectorized calculations consume their assembled dataset sources."""
        for dataset_id, dataset_calculations in calculations.items():
            for invocation in dataset_calculations:
                consumer = nodes[invocation.node_id]
                for source in dataset_sources.get(dataset_id, []):
                    graph.add_edge(nodes[source.node_id], consumer)

    def _add_write_dependencies(
        self,
        graph: graphable_.graph.Graph,
        nodes: dict[str, GraphNode],
        dataset_sources: dict[str, list[InvocationNode]],
        dataset_sinks: dict[str, list[InvocationNode]],
        calculations: dict[str, list[InvocationNode]],
    ) -> None:
        """Make dataset writes depend on their source fragments and relevant calculations."""
        for dataset_id, sinks in dataset_sinks.items():
            sources = dataset_sources.get(dataset_id, [])
            dataset_calculations = calculations.get(dataset_id, [])
            for sink in sinks:
                sink_node = nodes[sink.node_id]
                for source in sources:
                    graph.add_edge(nodes[source.node_id], sink_node)
                referenced = set(sink.input_features)
                dependencies = (
                    [
                        invocation
                        for invocation in dataset_calculations
                        if referenced.intersection(invocation.output_features)
                    ]
                    if referenced
                    else dataset_calculations
                )
                for invocation in dependencies:
                    graph.add_edge(nodes[invocation.node_id], sink_node)

    def dataset_for(self, node: InvocationNode) -> spec.Dataset:
        """Return a node's dataset directly from its declaring entity."""
        return self.spec.entities[node.entity_id].datasets[node.dataset_id]

    def mapping_for(self, node: InvocationNode) -> spec.Mapping:
        """Return the declaration that produced an invocation node."""
        return self.dataset_for(node).mappings[node.mapping_id]

    def topology(self) -> list[list[InvocationNode]]:
        """Return invocations grouped by dependency level (topological order)."""
        levels = self.graph.parallelized_topological_order()
        return [[level_node.reference for level_node in level] for level in levels]

    def subset(self, features: list[str]) -> InvocationGraph:
        """Return the dependency closure needed to produce selected features."""
        feature_producers = {
            feature: invocation
            for invocation in self.invocations
            for feature in invocation.output_features
            if feature not in self.spec.dimensions
        }
        missing = sorted(set(features) - set(feature_producers))
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        requested_nodes = [feature_producers[feature] for feature in features]
        selected_nodes = {self._node_by_key(node.node_id) for node in requested_nodes}
        for node in list(selected_nodes):
            selected_nodes.update(self.graph.ancestors(node))

        selected_dataset_ids = {node.dataset_id for node in requested_nodes}
        for invocation in self.invocations:
            if invocation.operation != operations.WRITE:
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
