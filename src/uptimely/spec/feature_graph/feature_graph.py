"""Describe feature dependencies as a graph and resolve requested outputs."""

import graphable as graphable_
from graphable import views

from uptimely.spec import arg_types, functions, validation
from uptimely.spec import model as spec_model
from uptimely.spec import references as bindings

from . import models

Node = graphable_.graphable.Graphable
FeatureGraphNodeMeta = models.FunctionNode | models.FeatureNode


class FeatureGraphBase:
    """Shared helpers for complete and subset feature graphs."""

    graph: graphable_.graph.Graph
    _node_index: dict[str, Node]
    _explicit_output_names: list[str] | None

    @staticmethod
    def _node_key(reference: FeatureGraphNodeMeta) -> str:
        """Return a stable node key from a feature name or function call."""
        return reference.node_id

    def _topology_items_for_level(
        self,
        level: list[Node],
        item_type: str,
    ) -> list[str | FeatureGraphNodeMeta | Node]:
        """Project one topology level into requested item representation."""
        if item_type == "feature_ref":
            return [
                node.reference for node in level if isinstance(node.reference, models.FeatureNode)
            ]
        if item_type == "feature_name":
            return [
                node.reference.name
                for node in level
                if isinstance(node.reference, models.FeatureNode)
            ]
        if item_type == "function":
            return [
                node.reference for node in level if isinstance(node.reference, models.FunctionNode)
            ]
        if item_type == "function_name":
            return [
                node.reference.name
                for node in level
                if isinstance(node.reference, models.FunctionNode)
            ]
        if item_type == "node":
            return level
        raise ValueError(f"Invalid item_type: {item_type}")

    def topology(
        self, item_type: str, skip_input: bool = False
    ) -> list[list[str | FeatureGraphNodeMeta | Node]]:
        """Return graph items grouped by dependency level."""
        levels = self.graph.parallelized_topological_order()

        if skip_input:
            levels = levels[1:]

        return [self._topology_items_for_level(level, item_type) for level in levels]

    def print_graph(self) -> str:
        """Print the dependency graph and return its text representation."""
        graph_text = self.render_graph()
        print(graph_text)
        return graph_text

    def render_graph(self) -> str:
        """Return a text representation of the dependency graph."""
        return views.texttree.create_topology_tree_txt(self.graph)

    @property
    def input_names(self) -> list[str]:
        """Source-provided inputs required by functions in this graph."""
        return sorted(
            node.reference.name
            for node in self.graph
            if isinstance(node.reference, models.FeatureNode) and node.reference.is_source_input
        )

    @property
    def feature_input_names(self) -> list[str]:
        """Raw features required by functions but not produced by one."""
        return self.input_names

    @property
    def output_names(self) -> list[str]:
        """Names of features exposed by this graph."""
        if self._explicit_output_names is not None:
            return self._explicit_output_names
        return sorted(self.feature_names)

    @property
    def feature_output_names(self) -> list[str]:
        """Names of features exposed by this graph."""
        return self.output_names

    @property
    def intermediate_names(self) -> set[str]:
        """Names of features considered intermediate for this graph."""
        if self._explicit_output_names is not None:
            return self.feature_names - set(self.input_names) - set(self.output_names)
        return {
            node.reference.name
            for node in self.graph
            if isinstance(node.reference, models.FeatureNode) and node.reference.is_intermediate
        }

    @property
    def feature_intermediate_names(self) -> set[str]:
        """Names of features considered intermediate for this graph."""
        return self.intermediate_names

    @property
    def feature_names(self) -> set[str]:
        """Names of all features produced by graph functions."""
        return {
            node.reference.name
            for node in self.graph
            if isinstance(node.reference, models.FeatureNode)
            and node.reference.is_output
            and not node.reference.is_source_input
        }


class FeatureGraph(FeatureGraphBase):
    """Global dependency graph built from all feature actions."""

    def __init__(self, spec: spec_model.Spec) -> None:
        """Build the complete dependency graph from spec declarations."""
        validation.validate_spec(spec)
        self.functions: list[spec_model.FunctionTemplate] = []
        self._graph_operations: list[
            tuple[spec_model.FunctionTemplate, str, str, list[str], list[str]]
        ] = []

        for entity_id, entity in spec.entities.items():
            for dataset in entity.datasets.values():
                for action_id, action in dataset.actions.items():
                    function = spec.functions[action.binding.function]
                    dependencies = action.input_features
                    if all(existing.id != function.id for existing in self.functions):
                        self.functions.append(function)
                    self._graph_operations.append(
                        (
                            function,
                            entity_id,
                            action_id,
                            [
                                feature_id
                                for feature_id in action.output_features
                                if feature_id not in spec.dimensions
                            ],
                            list(dict.fromkeys(dependencies)),
                        )
                    )

        self.spec = spec
        self._node_index: dict[str, Node] = {}
        self._explicit_output_names = None
        self.graph = self._create_graph()

    def _create_graph(self) -> graphable_.graph.Graph:
        """Build a graph from the loaded function call dependencies."""
        graph = graphable_.graph.Graph()
        nodes: dict[str, Node] = {}
        function_entities: dict[tuple[str, str, str | None], set[str]] = {}
        function_outputs: dict[tuple[str, str, str | None], set[str]] = {}
        for function, entity, action_id, outputs, _dependencies in self._graph_operations:
            function_key = (
                function.kind,
                function.id,
                action_id if function.kind == functions.ESCAPE else None,
            )
            function_entities.setdefault(function_key, set()).add(entity)
            function_outputs.setdefault(function_key, set()).update(outputs)

        output_names = {
            output
            for _function, _entity, _action_id, outputs, _dependencies in self._graph_operations
            for output in outputs
            if output not in self.spec.dimensions
        }
        dependency_names = {
            parent
            for function, _entity, _action_id, _outputs, dependencies in self._graph_operations
            for parent in dependencies
        }
        feature_metadata: dict[str, models.FeatureNode] = {}

        def register_feature_metadata(
            name: str,
            data_type: str | None,
            entity: str | None,
            *,
            is_source_input: bool = False,
        ) -> None:
            existing = feature_metadata.get(name)
            feature_metadata[name] = models.FeatureNode(
                name=name,
                data_type=(
                    existing.data_type if existing and existing.data_type is not None else data_type
                ),
                entity=existing.entity if existing and existing.entity is not None else entity,
                is_source_input=(
                    (existing.is_source_input if existing else False) or is_source_input
                ),
            )

        for entity_id, entity in self.spec.entities.items():
            for dataset in entity.datasets.values():
                for action in dataset.actions.values():
                    function_kind = bindings.action_kind(action, self.spec.functions)
                    for name in action.output_features:
                        feature = dataset.features[name]
                        register_feature_metadata(
                            name,
                            feature.type,
                            entity_id,
                            is_source_input=function_kind
                            not in {functions.COLLAPSE, functions.ESCAPE, functions.VECTORIZE},
                        )
        for function, entity, _action_id, outputs, _dependencies in self._graph_operations:
            for output in outputs:
                register_feature_metadata(
                    output,
                    None
                    if function.kind in {functions.ESCAPE, functions.VECTORIZE}
                    else arg_types.DATAFRAME,
                    entity,
                )

        def node(reference: FeatureGraphNodeMeta) -> Node:
            return nodes.setdefault(
                self._node_key(reference), graphable_.graphable.Graphable(reference)
            )

        def feature_meta(
            name: str,
            function: spec_model.FunctionTemplate | None = None,
            entity: str | None = None,
            data_type: str | None = None,
        ) -> models.FeatureNode:
            metadata = feature_metadata.get(name)
            return models.FeatureNode(
                name=name,
                data_type=(
                    None
                    if function is not None and function.kind == functions.VECTORIZE
                    else data_type or (metadata.data_type if metadata else None)
                ),
                entity=entity or (metadata.entity if metadata else None),
                is_input=name in dependency_names,
                is_output=name in output_names,
                is_source_input=metadata.is_source_input if metadata else False,
            )

        for function, entity, operation_id, outputs, dependencies in self._graph_operations:
            function_key = (
                function.kind,
                function.id,
                operation_id if function.kind == functions.ESCAPE else None,
            )
            entities = function_entities[function_key]
            function_node = node(
                models.FunctionNode(
                    name=function.id,
                    features=tuple(sorted(function_outputs[function_key])),
                    entity=next(iter(entities)) if len(entities) == 1 else None,
                    action_id=operation_id if function.kind == functions.ESCAPE else None,
                    function=function,
                )
            )

            for output in outputs:
                output_node = node(feature_meta(output, function, entity))
                graph.add_edge(function_node, output_node)

            for parent in set(dependencies):
                parent_node = node(feature_meta(parent))
                graph.add_edge(parent_node, function_node)

        self._node_index = nodes
        return graph

    def _get_ancestor_nodes(self, feature_names: list[str]) -> set[Node]:
        """Return the graph nodes required to vectorize the provided feature names."""
        requested_nodes = [self._node_index[fn] for fn in feature_names]
        subgraph_nodes = set(requested_nodes)

        for node in requested_nodes:
            ancestors = set(self.graph.ancestors(node))
            subgraph_nodes.update(ancestors)

        return subgraph_nodes

    def subset(self, output_names: list[str] | None = None) -> "FeatureSubGraph":
        """Create the minimal feature subgraph needed for requested outputs."""
        if output_names is None:
            output_names = sorted(self.feature_names)

        missing = [name for name in output_names if name not in self._node_index]
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        # Requested output nodes, intermediate nodes and input nodes
        nodes = self._get_ancestor_nodes(output_names)
        g = graphable_.graph.Graph(nodes, discover=False).clone(include_edges=True)
        return FeatureSubGraph(graph=g, output_names=output_names)


class FeatureSubGraph(FeatureGraphBase):
    """Feature dependency subset extracted from the complete feature graph."""

    def __init__(
        self,
        graph: graphable_.graph.Graph,
        output_names: list[str] | None,
    ) -> None:
        """Initialize a feature dependency subset and its explicit output targets."""
        self.graph = graph
        self._node_index = {self._node_key(n.reference): n for n in self.graph}
        self._explicit_output_names = (
            output_names if output_names is not None else sorted(self.feature_names)
        )
