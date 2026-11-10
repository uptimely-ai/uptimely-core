"""Describe feature dependencies as a graph and resolve requested outputs."""

import dataclasses

import graphable as graphable_
from graphable import views

from uptimely.spec import model as spec_model
from uptimely.spec import validation

from . import models

Node = graphable_.graphable.Graphable
FeatureGraphNodeMeta = models.OperatorNode | models.FeatureNode


class FeatureGraphBase:
    """Shared helpers for complete and subset feature graphs."""

    graph: graphable_.graph.Graph
    _node_index: dict[str, Node]
    _explicit_output_names: list[str] | None

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
        if item_type == "operator":
            return [
                node.reference for node in level if isinstance(node.reference, models.OperatorNode)
            ]
        if item_type == "operator_name":
            return [
                node.reference.operator_id
                for node in level
                if isinstance(node.reference, models.OperatorNode)
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
    def feature_nodes(self) -> tuple[models.FeatureNode, ...]:
        """Return feature metadata in the graph's current iteration order."""
        return tuple(
            node.reference for node in self.graph if isinstance(node.reference, models.FeatureNode)
        )

    @property
    def input_names(self) -> list[str]:
        """Source-provided inputs required by operator in this graph."""
        return sorted(feature.name for feature in self.feature_nodes if feature.is_source_input)

    @property
    def feature_input_names(self) -> list[str]:
        """Raw features required by operator but not produced by one."""
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
        return {feature.name for feature in self.feature_nodes if feature.is_intermediate}

    @property
    def feature_intermediate_names(self) -> set[str]:
        """Names of features considered intermediate for this graph."""
        return self.intermediate_names

    @property
    def feature_names(self) -> set[str]:
        """Names of all features produced by graph operator."""
        return {
            feature.name
            for feature in self.feature_nodes
            if feature.is_output and not feature.is_source_input
        }


class FeatureGraph(FeatureGraphBase):
    """Global dependency graph built from all feature operator."""

    def __init__(self, spec: spec_model.Spec, *, validate: bool = True) -> None:
        """Build the complete dependency graph from spec declarations.

        Args:
            spec: Spec document to represent.
            validate: Run semantic checks; disable only for an already validated Spec.
        """
        if validate:
            validation.validate_spec(spec)
        self.operators = spec.operators
        self.spec = spec
        self._node_index: dict[str, Node] = {}
        self._explicit_output_names = None
        self.graph = self._create_graph()

    def _declared_features(self) -> dict[str, models.FeatureNode]:
        """Resolve output metadata directly from operators and profile declarations."""
        feature_metadata: dict[str, models.FeatureNode] = {}
        for key, operator in self.spec.operator_items:
            profile = self.spec.operator_profiles[key]
            profile_id = self.spec.operator_profile_keys[key]
            function = self.spec.functions[operator.compute.function]
            has_target_dataframe = any(
                source_profile == profile_id
                for _, _, source_profile in self.spec.operator_dataframe_arguments[key]
            )
            is_source_input = (
                function.returns == "dataframe"
                and not has_target_dataframe
                and "collapse" not in self.spec.operator_grain_relationships[key].values()
            )
            for name in operator.output_features:
                if name in self.spec.key_ids_by_profile[key[0]]:
                    continue
                feature = profile.all_features[name]
                reference = models.FeatureNode(
                    name=name,
                    data_type=feature.type,
                    profile_id=profile_id,
                    display_name=feature.name,
                    profile_name=profile.name,
                    is_source_input=is_source_input,
                )
                existing = feature_metadata.get(name)
                if existing is not None:
                    reference = dataclasses.replace(
                        existing,
                        data_type=existing.data_type
                        if existing.data_type is not None
                        else reference.data_type,
                        display_name=existing.display_name
                        if existing.display_name is not None
                        else reference.display_name,
                        is_source_input=existing.is_source_input or is_source_input,
                    )
                feature_metadata[name] = reference
        return feature_metadata

    def _create_graph(self) -> graphable_.graph.Graph:
        """Connect declared feature inputs, operator, and non-dimension outputs."""
        graph = graphable_.graph.Graph()
        nodes: dict[str, Node] = {}
        output_names = {
            name
            for key, operator in self.spec.operator_items
            for name in operator.output_features
            if name not in self.spec.key_ids_by_profile[key[0]]
        }
        dependency_names = {
            name for _, operator in self.spec.operator_items for name in operator.input_features
        }
        feature_metadata = self._declared_features()

        def node(reference: FeatureGraphNodeMeta) -> Node:
            key = reference.node_id
            if key not in nodes:
                nodes[key] = graphable_.graphable.Graphable(reference)
            return nodes[key]

        def feature_meta(
            name: str,
            operator: models.OperatorNode | None = None,
        ) -> models.FeatureNode:
            metadata = feature_metadata.get(name, models.FeatureNode(name=name))
            display_name = metadata.display_name
            if not display_name:
                dimension_name = next(
                    (
                        dimension.name
                        for dimension in self.spec.dimensions.values()
                        if any(
                            resolution.key == name for resolution in dimension.resolutions.values()
                        )
                    ),
                    None,
                )
                display_name = dimension_name or name
            return dataclasses.replace(
                metadata,
                profile_id=operator.profile_id if operator is not None else metadata.profile_id,
                display_name=display_name,
                is_input=name in dependency_names,
                is_output=name in output_names,
            )

        for key, operator in self.spec.operator_items:
            profile = self.spec.operator_profiles[key]
            profile_id = self.spec.operator_profile_keys[key]
            outputs = [
                name
                for name in operator.output_features
                if name not in self.spec.key_ids_by_profile[key[0]]
            ]
            operator_metadata = models.OperatorNode(
                operator_id=operator.id,
                features=tuple(sorted(outputs)),
                profile_id=profile_id,
                profile_name=profile.name,
                operator=operator,
                function=self.spec.functions[operator.compute.function],
                execution_form=self.spec.operator_execution_forms[key],
                binding_roles=self.spec.operator_binding_roles[key],
                grain_relationships=tuple(
                    (
                        self.spec.profiles_by_key[source].id if source is not None else None,
                        relationship,
                    )
                    for source, relationship in self.spec.operator_grain_relationships[key].items()
                ),
                source_status=self.spec.operator_source_statuses[key],
                function_returns=self.spec.functions[operator.compute.function].returns,
            )
            operator_node = node(operator_metadata)
            for output in outputs:
                output_node = node(feature_meta(output, operator_metadata))
                graph.add_edge(operator_node, output_node)
            for parent in set(operator.input_features):
                if parent in self.spec.key_ids_by_profile[key[0]]:
                    continue
                parent_node = node(feature_meta(parent))
                graph.add_edge(parent_node, operator_node)

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

        nodes = self._get_ancestor_nodes(output_names)
        graph = graphable_.graph.Graph(nodes, discover=False).clone(include_edges=True)
        return FeatureSubGraph(graph=graph, output_names=output_names)


class FeatureSubGraph(FeatureGraphBase):
    """Feature dependency subset extracted from the complete feature graph."""

    def __init__(
        self,
        graph: graphable_.graph.Graph,
        output_names: list[str] | None,
    ) -> None:
        """Initialize a feature dependency subset and its explicit output targets."""
        self.graph = graph
        self._node_index = {node.reference.node_id: node for node in self.graph}
        self._explicit_output_names = (
            output_names if output_names is not None else sorted(self.feature_names)
        )
