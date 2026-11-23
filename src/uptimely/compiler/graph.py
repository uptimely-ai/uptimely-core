"""Generic dependency ordering for compiler-created invocation nodes."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Collection

import graphable as graphable_

from uptimely import plan, spec
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model

INVOCATION_LABEL_MAX_LENGTH = 24
INVOCATION_HASH_LENGTH = 10

type GraphNode = graphable_.graphable.Graphable


@dataclasses.dataclass(frozen=True)
class InvocationNode:
    """Compiler node with one resolved semantic contract and opaque graph ID."""

    semantics: plan.InvocationSemantics = dataclasses.field(compare=False, hash=False)
    arguments: dict[str, spec_model.BindingArgument] = dataclasses.field(
        default_factory=dict, compare=False, hash=False
    )
    _node_id: str = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Create a stable graph ID from the source call identity."""
        semantics = self.semantics
        identity = json.dumps(
            (
                semantics.function_id,
                semantics.profile_id,
                semantics.operator_id,
                semantics.role,
            ),
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:INVOCATION_HASH_LENGTH]
        label = re.sub(r"[^a-z0-9]+", "-", semantics.operator_id.lower()).strip("-") or "invocation"
        label = label[:INVOCATION_LABEL_MAX_LENGTH].rstrip("-")
        object.__setattr__(self, "_node_id", f"{label}--{fingerprint}")

    @property
    def node_id(self) -> str:
        """Return the deterministic opaque identifier used by the dependency graph."""
        return self._node_id

    def __str__(self) -> str:
        semantics = self.semantics
        return f"{semantics.role}:{semantics.function_id}({semantics.profile_id})"

    def __repr__(self) -> str:
        semantics = self.semantics
        return f"{semantics.role}:{semantics.function_id}({semantics.profile_id})"


class InvocationBuilder:
    """Create compiler invocation nodes from a validated Spec."""

    @staticmethod
    def create_nodes(spec_definition: spec.Spec) -> list[InvocationNode]:
        """Expand Spec operators into compute and merge invocation nodes."""
        invocations: list[InvocationNode] = []
        for key, operator in spec_definition.operator_items:
            profile_id = spec_definition.profiles_by_key[key[0]].id
            relationships = operator.grain_relationships(spec_definition, key)
            for role, binding in operator.bindings.items():
                function = spec_definition.functions[binding.function]
                dataframe_arity = sum(
                    arg_types.is_dataframe(argument.type) for argument in function.args.values()
                )
                if role == "compute" and dataframe_arity > 1:
                    raise ValueError(
                        f"Compute function {function.id} for operator {operator.id} "
                        "must declare at most one dataframe argument"
                    )
                if role == "merge" and dataframe_arity != 2:
                    raise ValueError(
                        f"Merge function {function.id} for operator {operator.id} "
                        "must declare exactly two dataframe arguments"
                    )
                is_compute = role == "compute"
                contract = operator.execution_contract(
                    returns=function.returns,
                    target_profile=key[0],
                    dataframe_sources=spec_definition.dataframe_argument_profiles[key],
                    grain_relationships={
                        source: relationship
                        for source, relationship in relationships.items()
                        if source is not None
                    },
                )
                if role == "merge":
                    result = "target"
                elif function.returns != "dataframe":
                    result = "none"
                elif operator.merge is not None:
                    result = "fragment"
                else:
                    result = "target"
                profile_key = spec_definition.profile_keys[profile_id]
                target_identifiers = spec_definition.identifiers_by_profile[profile_key]
                profile = spec_definition.profiles[profile_id]
                column_types = {
                    feature_id: feature.type
                    for feature_id, feature in profile.features.items()
                    if feature.type is not None
                } | spec_definition.identifier_types_by_profile[profile_key]
                key_types = spec_definition.key_types_by_profile[profile_key]
                column_types |= key_types
                output_features = tuple(operator.output_features) if is_compute else ()
                semantics = plan.InvocationSemantics(
                    role=role,
                    result=result,
                    produces_features=contract.produces_features if is_compute else False,
                    is_sink=(contract.is_sink or operator.is_workflow) if is_compute else False,
                    is_workflow=operator.is_workflow if is_compute else False,
                    is_seed=is_compute and profile.seed == operator.id,
                    dataframe_input_scope=(
                        contract.dataframe_input_scope if is_compute else "unrestricted"
                    ),
                    fragment_dimensions=(
                        contract.fragment_dimensions if is_compute else "not_applicable"
                    ),
                    row_count_relation=(
                        contract.row_count_relation if is_compute else "unrestricted"
                    ),
                    key_relation=contract.key_relation if is_compute else "unrestricted",
                    row_order_relation=(
                        contract.row_order_relation if is_compute else "unrestricted"
                    ),
                    existing_data_relation=(
                        contract.existing_data_relation if is_compute else "unrestricted"
                    ),
                    function_id=binding.function,
                    operator_id=operator.id,
                    profile_id=profile_id,
                    output_features=list(output_features),
                    input_features=list(operator.input_features) if is_compute else [],
                    row_context=operator.row_context if is_compute else None,
                    target_identifiers=list(target_identifiers),
                    fragment_keys=list(key_types),
                    output_types={
                        feature_id: column_types.get(feature_id) for feature_id in output_features
                    },
                    column_types=column_types,
                    argument_types={
                        argument_name: argument.type
                        for argument_name, argument in function.args.items()
                    },
                )
                invocations.append(
                    InvocationNode(
                        semantics=semantics,
                        arguments=binding.args,
                    )
                )

        nodes_by_id: dict[str, InvocationNode] = {}
        for invocation in invocations:
            previous = nodes_by_id.get(invocation.node_id)
            if previous is not None:
                previous_semantics = previous.semantics
                invocation_semantics = invocation.semantics
                raise ValueError(
                    f"Invocation ID collision {invocation.node_id!r} between operators "
                    f"{previous_semantics.profile_id!r}/{previous_semantics.operator_id!r} "
                    f"({previous_semantics.role}:{previous_semantics.function_id}) and "
                    f"{invocation_semantics.profile_id!r}/{invocation_semantics.operator_id!r} "
                    f"({invocation_semantics.role}:{invocation_semantics.function_id})"
                )
            nodes_by_id[invocation.node_id] = invocation
        return invocations


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
