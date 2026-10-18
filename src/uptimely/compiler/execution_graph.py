"""Describe callable invocation dependencies and resolve call ordering."""

from __future__ import annotations

import graphable as graphable_
from graphable.views import texttree

from uptimely import contracts, spec
from uptimely.spec import api as spec_api

from ..spec import references as bindings
from . import callable_node as callable_node_module

Node = graphable_.graphable.Graphable
NodeMeta = callable_node_module.CallableNode


class CallableGraph:
    """Dependency graph built from callable invocations and their feature dependencies."""

    def __init__(self, spec: spec.Spec) -> None:
        """Load spec functions and build the callable dependency graph.

        Args:
            spec: The spec document containing function declarations and invocations.
        """
        self.spec = spec
        prepared = spec_api.prepare_spec(spec)
        self._datasets = {
            (entity_id, dataset.id): dataset
            for entity_id, entity in spec.entities.items()
            for dataset in entity.datasets
        }
        self.calls = prepared.calls
        self.functions = [function for function in prepared.functions if function.role == "spec"]
        # Index all callables by (function_id, entity, feature) to resolve dependencies
        self._callable_index: dict[tuple[str, str, str], callable_node_module.CallableNode] = {}
        # Map feature names to the callables that produce them
        self._feature_producers: dict[str, callable_node_module.CallableNode] = {}
        self._dataset_sources: dict[tuple[str, str], list[callable_node_module.CallableNode]] = {}
        self._dataset_sinks: dict[tuple[str, str], list[callable_node_module.CallableNode]] = {}
        self.graph = self._create_graph()

    def _create_graph(self) -> graphable_.graph.Graph:
        """Build a graph where nodes are callables and edges represent feature dependencies."""
        nodes: dict[str, Node] = {}

        for entity_id, entity in self.spec.entities.items():
            for dataset in entity.datasets:
                dataset_key = (entity_id, dataset.id)
                for mapping in dataset.mappings.values():
                    operation = bindings.mapping_operation(mapping, self.spec.functions)
                    primary_feature = (
                        mapping.output_features[0] if mapping.output_features else None
                    )
                    call = next(
                        (
                            call
                            for call in self.calls
                            if call.entity == entity_id and call.feature in mapping.output_features
                        ),
                        None,
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
                        callable=call,
                        row_context=mapping.row_context,
                    )
                    nodes[node.node_id] = graphable_.graphable.Graphable(node)
                    if operation == "write":
                        self._dataset_sinks.setdefault(dataset_key, []).append(node)
                    elif operation != "vectorize":
                        self._dataset_sources.setdefault(dataset_key, []).append(node)
                    for feature in mapping.output_features:
                        if feature in self.spec.dimensions:
                            continue
                        self._feature_producers[feature] = node
                        if operation == "vectorize":
                            self._callable_index[(node.function_id, entity_id, feature)] = node
        graph = graphable_.graph.Graph(set(nodes.values()), discover=False)
        # Source transforms follow reads in their dataset.
        for fragments in self._dataset_sources.values():
            reads = [fragment for fragment in fragments if fragment.operation == "read"]
            downstream = [fragment for fragment in fragments if fragment.operation != "read"]
            for fragment in downstream:
                for read in reads:
                    graph.add_edge(nodes[read.node_id], nodes[fragment.node_id])

        # Mapping inputs create feature-level prerequisites.
        for graph_node in list(nodes.values()):
            consumer = graph_node.reference
            dataset = self.dataset_for(consumer)
            mapping = self.mapping_for(consumer)
            references = mapping.input_features
            dataset_references = bindings.dataset_dependencies(mapping.binding.args, dataset.id)
            for referenced_id in dataset_references:
                for source_node in nodes.values():
                    source = source_node.reference
                    if (
                        source.dataset_id == referenced_id
                        and source != consumer
                        and source.operation in contracts.FRAGMENT_OPERATIONS
                        and (referenced_id != dataset.id or source.operation == "read")
                    ):
                        graph.add_edge(source_node, graph_node)
            if consumer.operation == "collapse":
                source_id = self.collapse_input_dataset_id(consumer)
                for source_node in nodes.values():
                    source = source_node.reference
                    if source.dataset_id == source_id and (
                        source.operation in contracts.FRAGMENT_OPERATIONS
                        or (
                            source.operation == "vectorize"
                            and set(references).intersection(source.output_features)
                        )
                    ):
                        graph.add_edge(source_node, graph_node)
                continue
            for feature in references:
                producer = self._feature_producers.get(feature)
                if producer is not None and producer != consumer:
                    graph.add_edge(nodes[producer.node_id], graph_node)

        # Vectorize mappings consume the assembled dataset frame.
        for callable_node in set(self._callable_index.values()):
            consumer_node = nodes[callable_node.node_id]
            dataset_key = (callable_node.entity, callable_node.dataset_id)
            for source in self._dataset_sources.get(dataset_key, []):
                graph.add_edge(nodes[source.node_id], consumer_node)

        for dataset_key, sinks in self._dataset_sinks.items():
            sources = self._dataset_sources.get(dataset_key, [])
            calculations = list(
                dict.fromkeys(
                    node
                    for node in self._callable_index.values()
                    if (node.entity, node.dataset_id) == dataset_key
                )
            )
            for sink in sinks:
                sink_node = nodes[sink.node_id]
                for source in sources:
                    graph.add_edge(nodes[source.node_id], sink_node)
                referenced = set(self.mapping_for(sink).input_features)
                dependencies = (
                    [node for node in calculations if referenced.intersection(node.output_features)]
                    if referenced
                    else calculations
                )
                for calculation in dependencies:
                    graph.add_edge(nodes[calculation.node_id], sink_node)

        return graph

    def collapse_input_dataset_id(self, node: callable_node_module.CallableNode) -> str:
        """Infer the input dataset from a collapse node's spec binding."""
        if node.operation != "collapse" or node.mapping_id is None:
            raise ValueError(f"Expected a collapse mapping node: {node.node_id}")
        mapping = self.mapping_for(node)
        return bindings.collapse_input_dataset(self.spec, mapping)[1].id

    def dataset_for(self, node: callable_node_module.CallableNode) -> spec.Dataset:
        """Return a node's dataset from the validated entity-scoped index."""
        if node.dataset_id is None:
            raise ValueError(f"Callable node has no dataset: {node.node_id}")
        return self._datasets[node.entity, node.dataset_id]

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
        nodes = {
            graph_node
            for callable_node in requested_nodes
            for graph_node in [self._node_by_key(self._node_key(callable_node))]
        }
        for node in list(nodes):
            nodes.update(self.graph.ancestors(node))

        subset = self.__class__.__new__(self.__class__)
        subset.spec = self.spec
        subset._datasets = self._datasets
        subset.functions = self.functions
        subset._callable_index = self._callable_index
        subset._feature_producers = self._feature_producers
        subset._dataset_sources = self._dataset_sources
        subset._dataset_sinks = self._dataset_sinks
        selected_dataset_keys = {(node.entity, node.dataset_id) for node in requested_nodes}
        for dataset_key in selected_dataset_keys:
            for sink in self._dataset_sinks.get(dataset_key, []):
                sink_node = self._node_by_key(sink.node_id)
                nodes.add(sink_node)
                nodes.update(self.graph.ancestors(sink_node))
        subset.graph = graphable_.graph.Graph(nodes, discover=False).clone(include_edges=True)
        return subset

    def _node_by_key(self, node_key: str) -> Node:
        """Return a graph node using a callable node identifier."""
        for graph_node in self.graph:
            if self._node_key(graph_node.reference) == node_key:
                return graph_node
        raise ValueError(f"Callable node not found: {node_key}")

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
