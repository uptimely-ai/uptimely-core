"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import logging
from collections import abc

from uptimely import plan, spec
from uptimely.codebase.python import codebase, entrypoint
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model
from uptimely.spec import validation as spec_validation

from . import graph as invocation_graph

logger = logging.getLogger(__name__)


class Compiler:
    """Own Spec-to-plan strategy without retaining build state.

    The compiler expands operators into invocation nodes, resolves their feature and
    fragment dependencies, selects the requested graph, and determines its schedule.
    The graph module supplies generic dependency ordering; plan models represent and
    validate the resulting portable invocations and stages.
    """

    def compile(
        self,
        spec_definition: spec.Spec,
        features: abc.Collection[str] | None = None,
        *,
        signatures: abc.Mapping[str, entrypoint.Signature] | None = None,
        validate_spec: bool = True,
    ) -> plan.ExecutionPlan:
        """Compile a Spec by creating, selecting, scheduling, and serializing its invocations.

        This method owns the rules that turn operators into invocation nodes and
        connect their dependencies. It obtains a topological schedule from the
        generic invocation graph, checks implementation metadata, then converts
        each scheduled node to a portable plan invocation. The plan validates the
        compiler-selected schedule; it does not choose execution order.

        Args:
            spec_definition: The Spec document to compile.
            features: Optional collection of output feature identifiers.
            signatures: Optional return signatures inspected before compilation.
            validate_spec: Whether to validate the Spec during compilation.

        Returns:
            A portable execution plan for the selected invocation graph.

        Raises:
            ValueError: The Spec, feature selection, or implementation contract is invalid.
        """
        if validate_spec:
            spec_validation.validate_spec(spec_definition)
        if isinstance(features, str):
            logger.debug("Check feature selection is a collection, not a string")
            raise ValueError("features must be a collection of feature identifiers")
        signatures = dict(signatures or {})

        nodes = invocation_graph.InvocationBuilder.create_nodes(spec_definition)
        graph, feature_producers = self._create_invocation_graph(spec_definition, nodes)
        if features is not None:
            logger.debug("Selected features: %s", sorted(features))
            graph = self._select_invocations(
                spec_definition,
                graph,
                nodes,
                feature_producers,
                list(dict.fromkeys(features)),
            )
        else:
            logger.debug("Using all features")

        logger.debug("Validate dependency graph ordering")
        execution_stages = graph.topology()
        nodes = graph.invocations

        logger.debug("Validating %d invocations", len(nodes))
        selected_functions = self._collect_selected_functions(spec_definition, nodes)
        locations = dict.fromkeys(
            function.entrypoint for function in selected_functions.values() if function.entrypoint
        )
        logger.debug("Parse %d unique entrypoints", len(locations))
        python_codebase = codebase.Codebase.from_locations(
            locations, entrypoint_type=entrypoint.Entrypoint
        )
        entrypoints = python_codebase.entrypoints_index
        packages = self._read_plan_packages(entrypoints)
        logger.debug("Resolve structural argument references")
        invocations = self._create_plan_invocations(
            spec_definition,
            graph,
            nodes,
            selected_functions,
            signatures,
            packages,
        )
        stages = [[node.node_id for node in stage] for stage in execution_stages]

        logger.debug("Validate invocation IDs, dependencies, and execution stages")
        return plan.ExecutionPlan(
            plan_version=plan.PLAN_VERSION,
            required_backend="polars",
            invocations=invocations,
            stages=[plan.Stage(stage) for stage in stages],
        )

    @staticmethod
    def _create_invocation_graph(
        spec_definition: spec.Spec,
        invocations: list[invocation_graph.InvocationNode],
    ) -> tuple[
        invocation_graph.InvocationGraph,
        dict[str, invocation_graph.InvocationNode],
    ]:
        """Resolve Spec feature and fragment relationships into graph edges."""
        by_binding = {
            (
                node.semantics.profile_id,
                node.semantics.operator_id,
                node.semantics.role,
            ): node
            for node in invocations
        }
        feature_producers: dict[str, invocation_graph.InvocationNode] = {}
        dependencies: dict[str, set[str]] = {node.node_id: set() for node in invocations}
        dataset_publishers: dict[str, list[invocation_graph.InvocationNode]] = {}

        for node in invocations:
            semantics = node.semantics
            if semantics.role == "merge" or semantics.result == "target":
                dataset_publishers.setdefault(semantics.profile_id, []).append(node)
            if semantics.role != "compute":
                continue
            producer = node
            if semantics.result == "fragment":
                merge_node = by_binding.get((semantics.profile_id, semantics.operator_id, "merge"))
                if merge_node is not None:
                    dependencies[merge_node.node_id].add(node.node_id)
                    producer = merge_node
            if semantics.produces_features:
                for feature in semantics.output_features:
                    feature_producers[feature] = producer

        for node in invocations:
            semantics = node.semantics
            if semantics.role != "compute":
                continue
            for feature in semantics.input_features:
                producer = feature_producers.get(feature)
                if producer is not None and producer != node:
                    dependencies[node.node_id].add(producer.node_id)

        for node in invocations:
            semantics = node.semantics
            profile = spec_definition.profiles[semantics.profile_id]
            if profile.seed is None or semantics.operator_id == profile.seed:
                continue
            seed = by_binding[(semantics.profile_id, profile.seed, "compute")]
            if (
                semantics.role == "merge"
                or semantics.result == "target"
                or semantics.is_sink
                or semantics.dataframe_input_scope == "target"
            ):
                dependencies[node.node_id].add(seed.node_id)

        for key, operator in spec_definition.operator_items:
            profile_id = spec_definition.profiles_by_key[key[0]].id
            for role, binding in operator.bindings.items():
                node = by_binding.get((profile_id, operator.id, role))
                if node is None:
                    continue
                function = spec_definition.functions[binding.function]
                if role != "compute" or operator.input_features:
                    continue
                dataframe_arguments = function.arguments_by_type.get(arg_types.DATAFRAME, {})
                for argument_name in dataframe_arguments:
                    argument = binding.args.get(argument_name)
                    if argument is None:
                        continue
                    for source_id in argument.profile_dependencies(profile_id):
                        if source_id == profile_id:
                            continue
                        source_key = spec_definition.profile_keys.get(source_id)
                        if source_key is None:
                            continue
                        source_profile_id = spec_definition.profiles_by_key[source_key].id
                        for publisher in dataset_publishers.get(source_profile_id, ()):
                            if publisher == node:
                                continue
                            dependencies[node.node_id].add(publisher.node_id)
        return invocation_graph.InvocationGraph(invocations, dependencies), feature_producers

    @staticmethod
    def _select_invocations(
        spec_definition: spec.Spec,
        graph: invocation_graph.InvocationGraph,
        invocations: list[invocation_graph.InvocationNode],
        feature_producers: dict[str, invocation_graph.InvocationNode],
        features: list[str],
    ) -> invocation_graph.InvocationGraph:
        """Select requested outputs, their prerequisites, and matching sinks."""
        logger.debug("Select requested features and prerequisite invocations")
        selectable_features = feature_producers.keys() - spec_definition.key_ids
        missing = sorted(set(features) - selectable_features)
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        requested_nodes = {feature_producers[feature] for feature in features}
        selected_nodes = set(requested_nodes)
        for node in tuple(selected_nodes):
            selected_nodes.update(graph.ancestors(node.node_id))

        selected_profiles = {node.semantics.profile_id for node in requested_nodes}
        for node in invocations:
            semantics = node.semantics
            if (
                semantics.role == "compute"
                and semantics.is_sink
                and semantics.profile_id in selected_profiles
            ):
                selected_nodes.add(node)
                selected_nodes.update(graph.ancestors(node.node_id))
        return graph.subset([node.node_id for node in selected_nodes])

    @staticmethod
    def _collect_selected_functions(
        spec_definition: spec.Spec,
        nodes: list[invocation_graph.InvocationNode],
    ) -> dict[str, spec_model.FunctionTemplate]:
        """Validate entrypoints and collect each selected function once."""
        logger.debug("Validate function entrypoint declarations")
        logger.debug("Select unique functions for implementation checks")
        selected_functions: dict[str, spec_model.FunctionTemplate] = {}
        for node in nodes:
            function_id = node.semantics.function_id
            function = spec_definition.functions.get(function_id)
            if function is None or not function.entrypoint:
                raise ValueError(
                    f"Missing entrypoint for function {function_id} "
                    f"used by operator {node.semantics.operator_id}"
                )
            selected_functions.setdefault(function_id, function)
        return selected_functions

    @staticmethod
    def _read_plan_packages(
        entrypoints: abc.Mapping[str, entrypoint.Entrypoint],
    ) -> dict[str, plan.Package]:
        """Read portable package provenance once per entrypoint."""
        logger.debug("Resolve package ownership for %d unique entrypoints", len(entrypoints))
        packages: dict[str, plan.Package] = {}
        for location, implementation in entrypoints.items():
            try:
                provenance = implementation.read_package()
            except (ImportError, ValueError) as error:
                raise ValueError(
                    f"Could not read package provenance for entrypoint {location}: {error}"
                ) from error
            packages[location] = plan.Package(
                distribution=provenance.distribution,
                version=provenance.version,
            )
        return packages

    @staticmethod
    def _create_plan_invocations(
        spec_definition: spec.Spec,
        graph: invocation_graph.InvocationGraph,
        nodes: list[invocation_graph.InvocationNode],
        selected_functions: dict[str, spec_model.FunctionTemplate],
        signatures: dict[str, entrypoint.Signature],
        packages: dict[str, plan.Package],
    ) -> list[plan.Invocation]:
        """Convert scheduled nodes to portable invocations with resolved metadata."""
        logger.debug("Create portable invocations")
        invocations: list[plan.Invocation] = []
        for node in nodes:
            function = selected_functions[node.semantics.function_id]
            invocations.append(
                plan.Invocation.from_node(
                    spec_definition,
                    node,
                    dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
                    return_type=(
                        signatures[node.semantics.function_id].display.returns
                        if node.semantics.function_id in signatures
                        else None
                    ),
                    package=packages[function.entrypoint],
                )
            )
        return invocations
