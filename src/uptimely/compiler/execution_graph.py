"""Describe callable invocation dependencies and resolve call ordering."""

from __future__ import annotations

import graphable as graphable_
from graphable.views import texttree

from uptimely import contracts, spec
from uptimely.spec import validation

from ..spec import references as bindings
from . import callable_node as callable_node_module

type Node = graphable_.graphable.Graphable
NodeMeta = callable_node_module.CallableNode


class CallableGraph:
    """Dependency graph built from callable invocations and their feature dependencies."""

    def __init__(self, spec: spec.Spec) -> None:
        """Load spec functions and build the callable dependency graph.

        Args:
            spec: The spec document containing function declarations and invocations.
        """
        self.spec = spec
        validation.validate_spec(spec)
        # Map feature names to the callables that produce them
        self._feature_producers: dict[str, callable_node_module.CallableNode] = {}
        self._dataset_sources: dict[str, list[callable_node_module.CallableNode]] = {}
        self._dataset_sinks: dict[str, list[callable_node_module.CallableNode]] = {}
        self.graph = self._create_graph()
        self._nodes = {node.reference.node_id: node for node in self.graph}

    def _create_graph(self) -> graphable_.graph.Graph:
        """Build a graph where nodes are callables and edges represent feature dependencies."""
        nodes: dict[str, Node] = {}
        calculations: dict[str, list[callable_node_module.CallableNode]] = {}

        for entity_id, entity in self.spec.entities.items():
            for dataset in entity.datasets.values():
                for mapping in dataset.mappings.values():
                    operation = bindings.mapping_operation(mapping, self.spec.functions)
                    primary_feature = (
                        mapping.output_features[0] if mapping.output_features else None
                    )
                    node = callable_node_module.CallableNode(
                        function_id=mapping.binding.function,
                        entity=entity_id,
                        feature=primary_feature,
                        operation=operation,
                        dataset_id=dataset.id,
                        mapping_id=mapping.id,
                        output_features=tuple(mapping.output_features),
                        args=mapping.binding.args,
                        input_features=tuple(mapping.input_features),
                        row_context=mapping.row_context,
                    )
                    nodes[node.node_id] = graphable_.graphable.Graphable(node)
                    if operation == contracts.WRITE:
                        self._dataset_sinks.setdefault(dataset.id, []).append(node)
                    elif operation in contracts.FRAGMENT_OPERATIONS:
                        self._dataset_sources.setdefault(dataset.id, []).append(node)
                    elif operation == contracts.VECTORIZE:
                        calculations.setdefault(dataset.id, []).append(node)
                    for feature in mapping.output_features:
                        if feature in self.spec.dimensions:
                            continue
                        self._feature_producers[feature] = node
        graph = graphable_.graph.Graph(set(nodes.values()), discover=False)
        # Source transforms follow reads in their dataset.
        for fragments in self._dataset_sources.values():
            reads = [fragment for fragment in fragments if fragment.operation == contracts.READ]
            downstream = [
                fragment for fragment in fragments if fragment.operation != contracts.READ
            ]
            for fragment in downstream:
                for read in reads:
                    graph.add_edge(nodes[read.node_id], nodes[fragment.node_id])

        # Mapping inputs create feature-level prerequisites.
        for graph_node in nodes.values():
            consumer = graph_node.reference
            dataset = self.dataset_for(consumer)
            mapping = self.mapping_for(consumer)
            references = mapping.input_features
            dataset_references = bindings.dataset_dependencies(mapping.binding.args, dataset.id)
            for referenced_id in dataset_references:
                for source in self._dataset_sources.get(referenced_id, []):
                    if source != consumer and (
                        referenced_id != dataset.id or source.operation == contracts.READ
                    ):
                        graph.add_edge(nodes[source.node_id], graph_node)
            if consumer.operation == contracts.COLLAPSE:
                source_id = self.collapse_input_dataset_id(consumer)
                for source in self._dataset_sources.get(source_id, []):
                    graph.add_edge(nodes[source.node_id], graph_node)
                referenced_features = set(references)
                for source in calculations.get(source_id, []):
                    if referenced_features.intersection(source.output_features):
                        graph.add_edge(nodes[source.node_id], graph_node)
                continue
            for feature in references:
                producer = self._feature_producers.get(feature)
                if producer is not None and producer != consumer:
                    graph.add_edge(nodes[producer.node_id], graph_node)

        # Vectorize mappings consume the assembled dataset frame.
        for dataset_id, dataset_calculations in calculations.items():
            for callable_node in dataset_calculations:
                consumer_node = nodes[callable_node.node_id]
                for source in self._dataset_sources.get(dataset_id, []):
                    graph.add_edge(nodes[source.node_id], consumer_node)

        for dataset_id, sinks in self._dataset_sinks.items():
            sources = self._dataset_sources.get(dataset_id, [])
            dataset_calculations = calculations.get(dataset_id, [])
            for sink in sinks:
                sink_node = nodes[sink.node_id]
                for source in sources:
                    graph.add_edge(nodes[source.node_id], sink_node)
                referenced = set(self.mapping_for(sink).input_features)
                dependencies = (
                    [
                        node
                        for node in dataset_calculations
                        if referenced.intersection(node.output_features)
                    ]
                    if referenced
                    else dataset_calculations
                )
                for calculation in dependencies:
                    graph.add_edge(nodes[calculation.node_id], sink_node)

        return graph

    def collapse_input_dataset_id(self, node: callable_node_module.CallableNode) -> str:
        """Infer the input dataset from a collapse node's spec binding."""
        if node.operation != contracts.COLLAPSE or node.mapping_id is None:
            raise ValueError(f"Expected a collapse mapping node: {node.node_id}")
        mapping = self.mapping_for(node)
        return bindings.collapse_input_dataset(self.spec, mapping)[1].id

    def dataset_for(self, node: callable_node_module.CallableNode) -> spec.Dataset:
        """Return a node's dataset directly from its declaring entity."""
        if node.dataset_id is None:
            raise ValueError(f"Callable node has no dataset: {node.node_id}")
        return self.spec.entities[node.entity].datasets[node.dataset_id]

    def mapping_for(self, node: callable_node_module.CallableNode) -> spec.Mapping:
        """Return the declaration that produced a callable node."""
        if node.mapping_id is None:
            raise ValueError(f"Callable node has no mapping: {node.node_id}")
        return self.dataset_for(node).mappings[node.mapping_id]

    @staticmethod
    def _node_key(node: callable_node_module.CallableNode) -> str:
        """Return a stable node key for a callable."""
        return node.node_id

    def _node_data(self, node: callable_node_module.CallableNode) -> dict:
        """Build display metadata for a graph node."""
        return node.to_render_data()

    def topology(self) -> list[list[callable_node_module.CallableNode]]:
        """Return callables grouped by dependency level (topological order)."""
        levels = self.graph.parallelized_topological_order()
        return [[level_node.reference for level_node in level] for level in levels]

    def print_graph(self) -> str:
        """Return a text representation of the callable dependency graph."""
        graph_text = texttree.create_topology_tree_txt(self.graph)
        print(graph_text)
        return graph_text

    def print(self) -> None:
        """Print the callable dependency graph."""
        self.print_graph()

    def subset(self, features: list[str]) -> CallableGraph:
        """Return the dependency closure needed to produce selected features."""
        missing = sorted(set(features) - set(self._feature_producers))
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        requested_nodes = [self._feature_producers[feature] for feature in features]
        nodes = {self._node_by_key(node.node_id) for node in requested_nodes}
        for node in list(nodes):
            nodes.update(self.graph.ancestors(node))

        subset = self.__class__.__new__(self.__class__)
        subset.spec = self.spec
        subset._feature_producers = self._feature_producers
        subset._dataset_sources = self._dataset_sources
        subset._dataset_sinks = self._dataset_sinks
        selected_dataset_ids = {node.dataset_id for node in requested_nodes}
        for dataset_id in selected_dataset_ids:
            for sink in self._dataset_sinks.get(dataset_id, []):
                sink_node = self._node_by_key(sink.node_id)
                nodes.add(sink_node)
                nodes.update(self.graph.ancestors(sink_node))
        subset.graph = graphable_.graph.Graph(nodes, discover=False).clone(include_edges=True)
        subset._nodes = {node.reference.node_id: node for node in subset.graph}
        return subset

    def _node_by_key(self, node_key: str) -> Node:
        """Return a graph node using a callable node identifier."""
        try:
            return self._nodes[node_key]
        except KeyError as error:
            raise ValueError(f"Callable node not found: {node_key}") from error

    @property
    def callables(self) -> list[callable_node_module.CallableNode]:
        """All callable nodes in the graph."""
        return [node.reference for node in self.graph]

    def dependencies(
        self, node: callable_node_module.CallableNode
    ) -> list[callable_node_module.CallableNode]:
        """Return callables that directly produce the node's dependencies."""
        graph_node = self._node_by_key(node.node_id)
        return sorted(
            (dependency.reference for dependency in graph_node.depends_on),
            key=lambda dependency: dependency.node_id,
        )

    def get_callable_order(self) -> list[callable_node_module.CallableNode]:
        """Return callables in execution order (topological sort)."""
        all_callables = []
        for level in self.topology():
            all_callables.extend(level)
        return all_callables
