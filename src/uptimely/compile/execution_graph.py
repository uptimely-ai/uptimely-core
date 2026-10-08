"""Describe callable invocation dependencies and resolve call ordering."""

from graphable import graph as graphable_graph
from graphable import graphable

from uptimely.spec import Specification

from .node import SOURCE_OPERATION_TYPES, CallableNode

Node = graphable.Graphable
NodeMeta = CallableNode


class CallableGraph:
    """Dependency graph built from callable invocations and their feature dependencies."""

    def __init__(self, specs: Specification) -> None:
        """Load analytics functions and build the callable dependency graph.

        Args:
            specs: The specification containing all functions and their callable invocations.
        """
        self.specification = specs
        self.functions = [
            function for function in specs.resolved_functions if function.role == "analytics"
        ]
        # Index all callables by (function_id, entity, feature) to resolve dependencies
        self._callable_index: dict[tuple[str, str, str], CallableNode] = {}
        # Map feature names to the callables that produce them
        self._feature_producers: dict[str, CallableNode] = {}
        self._dataset_sources: dict[tuple[str, str], list[CallableNode]] = {}
        self._dataset_sinks: dict[tuple[str, str], list[CallableNode]] = {}
        self.graph = self._create_graph()

    def _create_graph(self) -> graphable_graph.Graph:
        """Build a graph where nodes are callables and edges represent feature dependencies."""
        graph = graphable_graph.Graph()
        nodes: dict[str, Node] = {}

        for entity_id, entity in self.specification.entities.items():
            for dataset in entity.datasets:
                dataset_key = (entity_id, dataset.id)
                for operation_type, source in dataset.fragment_operations:
                    node = CallableNode(
                        function_id=source.binding.function,
                        entity=entity_id,
                        operation_type=operation_type,
                        callable_type_override=operation_type,
                        dataset_id=dataset.id,
                        operation_id=source.id,
                        args=source.binding.args,
                    )
                    nodes[node.node_id] = graphable.Graphable(node)
                    self._dataset_sources.setdefault(dataset_key, []).append(node)
                    for feature in source.features:
                        if feature not in self.specification.dimensions:
                            self._feature_producers[feature] = node
                for sink in dataset.write.values():
                    node = CallableNode(
                        function_id=sink.binding.function,
                        entity=entity_id,
                        operation_type="write",
                        dataset_id=dataset.id,
                        operation_id=sink.id,
                        args=sink.binding.args,
                    )
                    nodes[node.node_id] = graphable.Graphable(node)
                    self._dataset_sinks.setdefault(dataset_key, []).append(node)

        # First pass: create all callable nodes and register feature producers
        for fragments in self._dataset_sources.values():
            reads = [fragment for fragment in fragments if fragment.operation_type == "read"]
            downstream = [fragment for fragment in fragments if fragment.operation_type != "read"]
            for fragment in downstream:
                for read in reads:
                    graph.add_edge(nodes[read.node_id], nodes[fragment.node_id])

        for fragments in self._dataset_sources.values():
            for fragment in fragments:
                for feature in self._feature_references(fragment.args):
                    producer = self._feature_producers.get(feature)
                    if producer is not None and producer != fragment:
                        graph.add_edge(nodes[producer.node_id], nodes[fragment.node_id])

        for function in self.functions:
            for call in function.callables:
                callable_node = CallableNode(
                    function_id=function.id,
                    entity=call.entity,
                    feature=call.feature,
                    operation_type="vectorize",
                    dataset_id=self._dataset_id(call.entity, call.feature),
                    args=call.args,
                    callable=call,
                )
                node_key = self._node_key(callable_node)
                nodes[node_key] = graphable.Graphable(callable_node)
                self._callable_index[(function.id, call.entity, call.feature)] = callable_node
                self._feature_producers[call.feature] = callable_node

        # Second pass: create edges based on feature dependencies
        for function in self.functions:
            for call in function.callables:
                callable_node = self._callable_index[(function.id, call.entity, call.feature)]
                consumer_node = nodes[self._node_key(callable_node)]

                dataset_key = (call.entity, callable_node.dataset_id)
                for source in self._dataset_sources.get(dataset_key, []):
                    graph.add_edge(nodes[source.node_id], consumer_node)

                # Add edges from producer callables to this consumer callable
                for parent_feature in call.depends_on_features:
                    if parent_feature in self._feature_producers:
                        producer_callable = self._feature_producers[parent_feature]
                        producer_node = nodes[self._node_key(producer_callable)]
                        graph.add_edge(producer_node, consumer_node)

        for dataset_key, sinks in self._dataset_sinks.items():
            sources = self._dataset_sources.get(dataset_key, [])
            calculations = [
                node
                for node in self._callable_index.values()
                if (node.entity, node.dataset_id) == dataset_key
            ]
            for sink in sinks:
                sink_node = nodes[sink.node_id]
                for source in sources:
                    graph.add_edge(nodes[source.node_id], sink_node)
                referenced = set(self._feature_references(sink.args))
                dependencies = (
                    [node for node in calculations if node.feature in referenced]
                    if referenced
                    else calculations
                )
                for calculation in dependencies:
                    graph.add_edge(nodes[calculation.node_id], sink_node)

        return graph

    def _dataset_id(self, entity_id: str, feature: str) -> str | None:
        """Return the dataset that owns a feature."""
        entity = self.specification.entities.get(entity_id)
        if entity is None:
            return None
        for dataset in entity.datasets:
            if feature in dataset.vectorize:
                return dataset.id
        return None

    @staticmethod
    def _feature_references(value: object) -> list[str]:
        """Return feature references nested in operation arguments."""
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, str) and value.startswith("$features."):
            return [value.removeprefix("$features.")]
        if isinstance(value, dict):
            return [
                feature
                for item in value.values()
                for feature in CallableGraph._feature_references(item)
            ]
        if isinstance(value, list):
            return [
                feature for item in value for feature in CallableGraph._feature_references(item)
            ]
        return []

    @staticmethod
    def _node_key(node: CallableNode) -> str:
        """Return a stable node key for a callable."""
        return node.node_id

    def _node_data(self, node: CallableNode) -> dict:
        """Build display metadata for a graph node."""
        return node.to_render_data()

    def topology(self) -> list[list[CallableNode]]:
        """Return callables grouped by dependency level (topological order)."""
        levels = self.graph.parallelized_topological_order()
        return [[level_node.reference for level_node in level] for level in levels]

    def print_graph(self) -> str:
        """Return a text representation of the callable dependency graph."""
        from graphable.views import texttree

        graph_text = texttree.create_topology_tree_txt(self.graph)
        print(graph_text)
        return graph_text

    def print(self) -> None:
        """Print the callable dependency graph."""
        self.print_graph()

    def subset(self, features: list[str]) -> "CallableGraph":
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
        subset.specification = self.specification
        subset.functions = self.functions
        subset._callable_index = self._callable_index
        subset._feature_producers = self._feature_producers
        subset._dataset_sources = self._dataset_sources
        subset._dataset_sinks = self._dataset_sinks
        selected_dataset_keys = {(node.entity, node.dataset_id) for node in requested_nodes}
        for dataset_key in selected_dataset_keys:
            for sink in self._dataset_sinks.get(dataset_key, []):
                nodes.add(self._node_by_key(sink.node_id))
        subset.graph = graphable_graph.Graph(nodes, discover=False).clone(include_edges=True)
        return subset

    def _node_by_key(self, node_key: str) -> Node:
        """Return a graph node using a callable node identifier."""
        for graph_node in self.graph:
            if self._node_key(graph_node.reference) == node_key:
                return graph_node
        raise ValueError(f"Callable node not found: {node_key}")

    @property
    def callables(self) -> list[CallableNode]:
        """All callable nodes in the graph."""
        return [node.reference for node in self.graph]

    def dependencies(self, node: CallableNode) -> list[CallableNode]:
        """Return callables that directly produce the node's dependencies."""
        graph_nodes = set(self.callables)
        dataset_key = (node.entity, node.dataset_id)
        if node.operation_type in SOURCE_OPERATION_TYPES:
            return []
        if node.operation_type in ("sink", "write"):
            sources = [
                source
                for source in self._dataset_sources.get(dataset_key, [])
                if source in graph_nodes
            ]
            referenced = set(self._feature_references(node.args))
            calculations = [
                producer
                for feature in referenced
                if (producer := self._feature_producers.get(feature)) in graph_nodes
            ]
            return [*sources, *calculations]

        dependencies = [
            source for source in self._dataset_sources.get(dataset_key, []) if source in graph_nodes
        ]
        if node.callable is not None:
            dependencies.extend(
                producer
                for feature in node.callable.depends_on_features
                if (producer := self._feature_producers.get(feature)) in graph_nodes
            )
        return list(dict.fromkeys(dependencies))

    def get_callable_order(self) -> list[CallableNode]:
        """Return callables in execution order (topological sort)."""
        all_callables = []
        for level in self.topology():
            all_callables.extend(level)
        return all_callables
