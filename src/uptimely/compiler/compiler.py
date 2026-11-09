"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import logging
from collections import abc

from uptimely import entrypoint, spec
from uptimely import plan as plan_module
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds as functions
from uptimely.spec import validation as spec_validation
from uptimely.spec.validation import errors

from . import graph as invocation_graph
from . import validation

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
    ) -> plan_module.ExecutionPlan:
        """Compile a Spec by creating, selecting, scheduling, and serializing its invocations.

        This method owns the rules that turn operators into invocation nodes and
        connect their dependencies. It obtains a topological schedule from the
        generic invocation graph, checks implementation metadata, then converts
        each scheduled node to a portable plan invocation. The plan validates the
        compiler-selected schedule; it does not choose execution order.

        Args:
            spec_definition: The Spec document to compile.
            features: Optional collection of output feature identifiers.

        Returns:
            A portable execution plan for the selected invocation graph.

        Raises:
            ValueError: The Spec, feature selection, or implementation contract is invalid.
        """
        spec_validation.validate_spec(spec_definition)
        validation.validation_feature_selection(features)

        nodes = self._create_invocation_nodes(spec_definition)
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

        logger.debug("Check dependency graph is acyclic and schedulable")
        execution_stages = graph.topology()
        nodes = graph.invocations

        logger.debug("Validating %d invocations", len(nodes))
        selected_functions, first_node_by_function = self._collect_selected_functions(
            spec_definition, nodes
        )
        locations = dict.fromkeys(
            function.entrypoint for function in selected_functions.values() if function.entrypoint
        )
        entrypoints = self._parse_entrypoints(locations)
        packages = self._read_package_provenance(entrypoints)
        signatures = self._validate_signatures(
            selected_functions,
            first_node_by_function,
            entrypoints,
            packages,
        )
        logger.debug("Check structural argument references resolve")
        invocations = self._create_plan_invocations(
            spec_definition,
            graph,
            nodes,
            selected_functions,
            signatures,
            packages,
        )
        stages = [[node.node_id for node in stage] for stage in execution_stages]

        logger.debug("Check emitted invocation IDs, dependencies, and stage ordering")
        return plan_module.ExecutionPlan(
            plan_version=plan_module.PLAN_VERSION,
            required_backend="polars",
            invocations=invocations,
            stages=[plan_module.Stage(stage) for stage in stages],
        )

    @staticmethod
    def _collect_selected_functions(
        spec_definition: spec.Spec,
        nodes: list[invocation_graph.InvocationNode],
    ) -> tuple[
        dict[str, spec_model.FunctionTemplate],
        dict[str, invocation_graph.InvocationNode],
    ]:
        """Validate entrypoints and collect each selected function once."""
        logger.debug("Check functions declare entrypoints")
        logger.debug("Selecting unique functions for implementation checks")
        selected_functions: dict[str, spec_model.FunctionTemplate] = {}
        first_node_by_function: dict[str, invocation_graph.InvocationNode] = {}
        for node in nodes:
            function = spec_definition.functions.get(node.function_id)
            if function is None or not function.entrypoint:
                raise ValueError(
                    f"Missing entrypoint for function {node.function_id} "
                    f"used by operator {node.operator_id}"
                )
            selected_functions.setdefault(node.function_id, function)
            first_node_by_function.setdefault(node.function_id, node)
        return selected_functions, first_node_by_function

    @staticmethod
    def _parse_entrypoints(
        locations: abc.Iterable[str],
    ) -> dict[str, entrypoint.Entrypoint]:
        """Parse and validate the selected implementation locations."""
        locations = list(locations)
        logger.debug("Check syntax for %d unique entrypoints", len(locations))
        entrypoints: dict[str, entrypoint.Entrypoint] = {}
        for location in locations:
            try:
                entrypoints[location] = entrypoint.Entrypoint(location)
            except ValueError as error:
                raise ValueError(f"Invalid entrypoint {location!r}: {error}") from error
        return entrypoints

    @staticmethod
    def _read_package_provenance(
        entrypoints: dict[str, entrypoint.Entrypoint],
    ) -> dict[str, plan_module.Package]:
        """Read portable package provenance once per entrypoint."""
        logger.debug("Check package ownership for %d unique entrypoints", len(entrypoints))
        packages: dict[str, plan_module.Package] = {}
        for location, implementation in entrypoints.items():
            try:
                provenance = implementation.read_package()
            except (ImportError, ValueError) as error:
                raise ValueError(
                    f"Could not read package provenance for entrypoint {location}: {error}"
                ) from error
            packages[location] = plan_module.Package(
                distribution=provenance.distribution,
                version=provenance.version,
            )
        return packages

    @staticmethod
    def _validate_signatures(
        selected_functions: dict[str, spec_model.FunctionTemplate],
        first_node_by_function: dict[str, invocation_graph.InvocationNode],
        entrypoints: dict[str, entrypoint.Entrypoint],
        packages: dict[str, plan_module.Package],
    ) -> dict[str, entrypoint.Signature]:
        """Read and validate each enabled function's implementation signature."""
        enabled_count = sum(function.validate_signature for function in selected_functions.values())
        disabled_count = sum(
            not function.validate_signature for function in selected_functions.values()
        )
        logger.debug("Check callable signatures for %d functions", enabled_count)
        logger.debug("Check implementations accept declared arguments")
        logger.debug("Check declared arguments can be passed as keywords")
        logger.debug("Check declared implementation argument annotations")
        logger.debug("Check required implementation parameters are declared")
        logger.debug("Check declared implementation return annotations")
        if disabled_count:
            logger.debug("Skipping %d functions (validate_signature=false)", disabled_count)

        signatures: dict[str, entrypoint.Signature] = {}
        for function_id, function in selected_functions.items():
            if not function.validate_signature:
                continue
            signatures[function_id] = Compiler._validate_function_signature(
                function,
                first_node_by_function[function_id],
                entrypoints[function.entrypoint],
                packages[function.entrypoint],
            )
        return signatures

    @staticmethod
    def _validate_function_signature(
        function: spec_model.FunctionTemplate,
        node: invocation_graph.InvocationNode,
        implementation: entrypoint.Entrypoint,
        package: plan_module.Package,
    ) -> entrypoint.Signature:
        """Read one implementation signature and check it against the Spec."""
        try:
            signature = implementation.read_signature()
            validation.validation_callable_signature(
                validation.CallableValidationContext(function, signature)
            )
        except errors.SpecError:
            raise
        except (ImportError, AttributeError, ValueError, TypeError, NameError) as error:
            raise ValueError(
                f"Could not read signature of function {function.id} "
                f"used by operator {node.operator_id} from entrypoint "
                f"{function.entrypoint}; available build package: {package}: {error}"
            ) from error
        return signature

    @staticmethod
    def _create_plan_invocations(
        spec_definition: spec.Spec,
        graph: invocation_graph.InvocationGraph,
        nodes: list[invocation_graph.InvocationNode],
        selected_functions: dict[str, spec_model.FunctionTemplate],
        signatures: dict[str, entrypoint.Signature],
        packages: dict[str, plan_module.Package],
    ) -> list[plan_module.Invocation]:
        """Convert scheduled nodes to portable invocations with resolved metadata."""
        logger.debug("Creating portable invocation representations")
        invocations: list[plan_module.Invocation] = []
        for node in nodes:
            function = selected_functions[node.function_id]
            invocations.append(
                plan_module.Invocation.from_node(
                    spec_definition,
                    node,
                    dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
                    return_type=(
                        signatures[node.function_id].returns
                        if node.function_id in signatures
                        else None
                    ),
                    package=packages[function.entrypoint],
                )
            )
        return invocations

    @staticmethod
    def _create_invocation_nodes(
        spec_definition: spec.Spec,
    ) -> list[invocation_graph.InvocationNode]:
        """Expand Spec operators into compiler-owned compute and merge nodes."""
        invocations: list[invocation_graph.InvocationNode] = []
        for key, operator in spec_definition.operator_items:
            profile_id = spec_definition.profiles_by_key[key[0]].id
            operator_kind = spec_definition.operator_kinds[key]
            compute_function = spec_definition.functions[operator.compute.function]
            compute_dataframe_arity = sum(
                arg_types.is_dataframe(argument.type) for argument in compute_function.args.values()
            )
            if compute_dataframe_arity > 1:
                raise ValueError(
                    f"Compute function {compute_function.id} for operator {operator.id} "
                    "must declare at most one dataframe argument"
                )
            result = (
                "none"
                if compute_function.returns != "dataframe"
                else "fragment"
                if operator.merge is not None
                else "target"
            )
            invocations.append(
                invocation_graph.InvocationNode(
                    function_id=operator.compute.function,
                    profile_id=profile_id,
                    operator_id=operator.id,
                    operator_kind=operator_kind,
                    role="compute",
                    result=result,
                    output_features=tuple(operator.output_features),
                    arguments=operator.compute.args,
                    input_features=tuple(operator.input_features),
                    row_context=operator.row_context,
                )
            )
            if operator.merge is not None:
                merge_function = spec_definition.functions[operator.merge.function]
                merge_dataframe_arity = sum(
                    arg_types.is_dataframe(argument.type)
                    for argument in merge_function.args.values()
                )
                if merge_dataframe_arity != 2:
                    raise ValueError(
                        f"Merge function {merge_function.id} for operator {operator.id} "
                        "must declare exactly two dataframe arguments"
                    )
                invocations.append(
                    invocation_graph.InvocationNode(
                        function_id=operator.merge.function,
                        profile_id=profile_id,
                        operator_id=operator.id,
                        operator_kind=operator_kind,
                        role="merge",
                        result="target",
                        arguments=operator.merge.args,
                    )
                )

        nodes_by_id: dict[str, invocation_graph.InvocationNode] = {}
        for invocation in invocations:
            previous = nodes_by_id.get(invocation.node_id)
            if previous is not None:
                raise ValueError(
                    f"Invocation ID collision {invocation.node_id!r} between operators "
                    f"{previous.profile_id!r}/{previous.operator_id!r} "
                    f"({previous.operator_kind}:{previous.function_id}) and "
                    f"{invocation.profile_id!r}/{invocation.operator_id!r} "
                    f"({invocation.operator_kind}:{invocation.function_id})"
                )
            nodes_by_id[invocation.node_id] = invocation
        return invocations

    @staticmethod
    def _create_invocation_graph(
        spec_definition: spec.Spec,
        invocations: list[invocation_graph.InvocationNode],
    ) -> tuple[
        invocation_graph.InvocationGraph,
        dict[str, invocation_graph.InvocationNode],
    ]:
        """Resolve Spec feature and fragment relationships into graph edges."""
        by_binding = {(node.profile_id, node.operator_id, node.role): node for node in invocations}
        feature_producers: dict[str, invocation_graph.InvocationNode] = {}
        dependencies: dict[str, set[str]] = {node.node_id: set() for node in invocations}
        dataset_publishers: dict[str, list[invocation_graph.InvocationNode]] = {}

        for node in invocations:
            if node.role == "merge" or node.result == "target":
                dataset_publishers.setdefault(node.profile_id, []).append(node)
            if node.role != "compute":
                continue
            definition = functions.OPERATOR_KINDS[node.operator_kind]
            producer = node
            if node.result == "fragment":
                merge_node = by_binding.get((node.profile_id, node.operator_id, "merge"))
                if merge_node is not None:
                    dependencies[merge_node.node_id].add(node.node_id)
                    producer = merge_node
            if definition.produces_features:
                for feature in node.output_features:
                    feature_producers[feature] = producer

        for node in invocations:
            if node.role != "compute":
                continue
            for feature in node.input_features:
                producer = feature_producers.get(feature)
                if producer is not None and producer != node:
                    dependencies[node.node_id].add(producer.node_id)

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
        logger.debug("Check selected output features have producers")
        selectable_features = feature_producers.keys() - spec_definition.grain_key_ids
        missing = sorted(set(features) - selectable_features)
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(missing))

        requested_nodes = {feature_producers[feature] for feature in features}
        selected_nodes = set(requested_nodes)
        for node in tuple(selected_nodes):
            selected_nodes.update(graph.ancestors(node.node_id))

        selected_profiles = {node.profile_id for node in requested_nodes}
        for node in invocations:
            if (
                node.role == "compute"
                and functions.OPERATOR_KINDS[node.operator_kind].is_sink
                and node.profile_id in selected_profiles
            ):
                selected_nodes.add(node)
                selected_nodes.update(graph.ancestors(node.node_id))
        return graph.subset([node.node_id for node in selected_nodes])
