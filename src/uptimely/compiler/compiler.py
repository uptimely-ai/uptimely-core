"""Compile a loaded Spec into a portable execution plan."""

from __future__ import annotations

import dataclasses
import logging
from collections import abc

from uptimely import plan, spec
from uptimely.codebase.python import codebase, entrypoint
from uptimely.spec import arg_types
from uptimely.spec import model as spec_model
from uptimely.spec import validation as spec_validation
from uptimely.spec.model import profile as profile_module

from . import graph as invocation_graph
from . import semantics as semantics_module

logger = logging.getLogger(__name__)

type _InvocationBinding = tuple[invocation_graph.InvocationNode, plan.InvocationSemantics]


@dataclasses.dataclass(frozen=True)
class _OperatorInvocations:
    """An operator and the invocation contracts created from its bindings."""

    profile: spec.Profile
    operator: spec.Operator
    bindings: dict[profile_module.OperatorBindingRole.Value, _InvocationBinding]

    @property
    def fragment_merge(self) -> _InvocationBinding | None:
        """Return the merge that publishes this operator's fragment, if any."""
        _, compute = self.bindings[profile_module.OperatorBindingRole.COMPUTE]
        if compute.result == plan.InvocationResultKind.FRAGMENT:
            return self.bindings.get(profile_module.OperatorBindingRole.MERGE)
        return None


@dataclasses.dataclass(frozen=True)
class _Publishers:
    """Invocation IDs that publish features, datasets, and profile seeds."""

    features: dict[str, str]
    datasets: dict[str, list[str]]
    seeds: dict[str, str]


class Compiler:
    """Own Spec-to-plan strategy without retaining build state.

    The compiler expands operators into invocations, resolves dependencies,
    selects a graph, and determines its schedule. Semantic contracts are derived
    separately from the Spec.
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

        Semantic resolution supplies invocation contracts. The compiler resolves
        their dependencies, then the generic invocation graph supplies the schedule.
        Plan models validate the resulting portable invocations and stages.

        Args:
            spec_definition: The Spec document to compile.
            features: Optional collection of output feature identifiers.
            signatures: Optional return signatures inspected before compilation.
            validate_spec: Whether to validate the Spec during compilation. If false,
                the caller must provide an already validated Spec.

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

        operators = self._create_invocations(spec_definition)
        bindings = [binding for operator in operators for binding in operator.bindings.values()]
        nodes = [node for node, _ in bindings]
        semantics_by_id = {node.node_id: semantics for node, semantics in bindings}
        publishers = self._index_publishers(operators)
        dependencies = self._resolve_dependencies(spec_definition, operators, publishers)
        graph = invocation_graph.InvocationGraph(nodes, dependencies)
        if features is not None:
            logger.debug("Selected features: %s", sorted(features))
            logger.debug("Select requested features and prerequisite invocations")
            selected = self._select_invocations(
                spec_definition, semantics_by_id, publishers.features, features
            )
            for invocation_id in tuple(selected):
                selected.update(node.node_id for node in graph.ancestors(invocation_id))
            graph = graph.subset(selected)
        else:
            logger.debug("Using all features")

        logger.debug("Validate dependency graph ordering")
        execution_stages = graph.topology()
        nodes = graph.invocations

        logger.debug("Validating %d invocations", len(nodes))
        selected_functions = self._collect_selected_functions(
            spec_definition, nodes, semantics_by_id
        )
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
            semantics_by_id,
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
    def _create_invocations(spec_definition: spec.Spec) -> list[_OperatorInvocations]:
        """Create invocation nodes and contracts for each operator."""
        operators: list[_OperatorInvocations] = []
        seen: dict[str, plan.InvocationSemantics] = {}
        for key, operator in spec_definition.operator_items:
            profile = spec_definition.profiles_by_key[key[0]]
            contracts = semantics_module.InvocationSemanticsBuilder.build(
                spec_definition, key, operator
            )
            bindings: dict[profile_module.OperatorBindingRole.Value, _InvocationBinding] = {}
            for role, semantics in contracts.items():
                invocation_id = invocation_graph.InvocationNode.create_id(
                    semantics.function_id, profile.id, operator.id, role
                )
                previous = seen.get(invocation_id)
                if previous is not None:
                    raise ValueError(
                        f"Invocation ID collision {invocation_id!r} between operators "
                        f"{previous.profile_id!r}/{previous.operator_id!r} "
                        f"({previous.role}:{previous.function_id}) and "
                        f"{profile.id!r}/{operator.id!r} "
                        f"({semantics.role}:{semantics.function_id})"
                    )
                seen[invocation_id] = semantics
                bindings[role] = (invocation_graph.InvocationNode(invocation_id), semantics)
            operators.append(_OperatorInvocations(profile, operator, bindings))
        return operators

    @staticmethod
    def _index_publishers(operators: list[_OperatorInvocations]) -> _Publishers:
        """Index the invocations that make features and datasets available."""
        features: dict[str, str] = {}
        datasets: dict[str, list[str]] = {}
        seeds: dict[str, str] = {}
        for item in operators:
            compute, contract = item.bindings[profile_module.OperatorBindingRole.COMPUTE]
            merge = item.fragment_merge
            publisher = merge[0].node_id if merge is not None else compute.node_id
            if contract.produces_features:
                for feature in item.operator.output_features:
                    features[feature] = publisher
            for node, semantics in item.bindings.values():
                if semantics.result == plan.InvocationResultKind.TARGET:
                    datasets.setdefault(item.profile.id, []).append(node.node_id)
                if semantics.is_seed:
                    seeds[item.profile.id] = node.node_id
        return _Publishers(features, datasets, seeds)

    @classmethod
    def _resolve_dependencies(
        cls,
        spec_definition: spec.Spec,
        operators: list[_OperatorInvocations],
        publishers: _Publishers,
    ) -> dict[str, set[str]]:
        """Connect each operator's invocations to their prerequisites."""
        dependencies: dict[str, set[str]] = {}
        for item in operators:
            for node, semantics in item.bindings.values():
                dependencies[node.node_id] = set()
                if cls._requires_seed(item, semantics):
                    dependencies[node.node_id].add(publishers.seeds[item.profile.id])

            compute, _ = item.bindings[profile_module.OperatorBindingRole.COMPUTE]
            dependencies[compute.node_id].update(
                cls._input_dependencies(spec_definition, item, publishers, compute.node_id)
            )
            merge = item.fragment_merge
            if merge is not None:
                dependencies[merge[0].node_id].add(compute.node_id)
        return dependencies

    @staticmethod
    def _requires_seed(item: _OperatorInvocations, semantics: plan.InvocationSemantics) -> bool:
        """Determine whether an invocation requires its profile's initialized dataset."""
        return (
            item.profile.seed is not None
            and item.operator.id != item.profile.seed
            and (
                semantics.result == plan.InvocationResultKind.TARGET
                or semantics.is_sink
                or semantics.dataframe_input_scope == profile_module.DataFrameInputScope.TARGET
            )
        )

    @classmethod
    def _input_dependencies(
        cls,
        spec_definition: spec.Spec,
        item: _OperatorInvocations,
        publishers: _Publishers,
        invocation_id: str,
    ) -> set[str]:
        """Resolve the publishers of an operator's feature or dataframe inputs."""
        if item.operator.input_features:
            dependencies = {
                publishers.features[feature]
                for feature in item.operator.input_features
                if feature in publishers.features
            }
        else:
            sources = cls._foreign_dataframe_profiles(
                spec_definition, item.operator, item.profile.id
            )
            dependencies = {
                publisher for source in sources for publisher in publishers.datasets.get(source, ())
            }
        dependencies.discard(invocation_id)
        return dependencies

    @staticmethod
    def _foreign_dataframe_profiles(
        spec_definition: spec.Spec, operator: spec.Operator, profile_id: str
    ) -> set[str]:
        """Find foreign datasets read by an operator without feature inputs."""
        source_ids: set[str] = set()
        binding = operator.compute
        function = spec_definition.functions[binding.function]
        for argument_name in function.arguments_by_type.get(arg_types.DATAFRAME, {}):
            argument = binding.args.get(argument_name)
            if argument is None:
                continue
            for source_id in argument.profile_dependencies(profile_id):
                if source_id != profile_id and source_id in spec_definition.profile_keys:
                    source_ids.add(source_id)
        return source_ids

    @staticmethod
    def _select_invocations(
        spec_definition: spec.Spec,
        semantics_by_id: abc.Mapping[str, plan.InvocationSemantics],
        feature_producers: abc.Mapping[str, str],
        features: abc.Collection[str],
    ) -> set[str]:
        """Select feature publishers and sinks in their target profiles."""
        selectable_features = feature_producers.keys() - spec_definition.key_ids
        missing = set(features) - selectable_features
        if missing:
            raise ValueError("Unknown output feature(s): " + ", ".join(sorted(missing)))
        selected = {feature_producers[feature] for feature in features}
        selected_profiles = {semantics_by_id[item].profile_id for item in selected}
        selected.update(
            invocation_id
            for invocation_id, semantics in semantics_by_id.items()
            if semantics.role == profile_module.OperatorBindingRole.COMPUTE
            and semantics.is_sink
            and semantics.profile_id in selected_profiles
        )
        return selected

    @staticmethod
    def _collect_selected_functions(
        spec_definition: spec.Spec,
        nodes: list[invocation_graph.InvocationNode],
        semantics_by_id: abc.Mapping[str, plan.InvocationSemantics],
    ) -> dict[str, spec_model.FunctionTemplate]:
        """Validate entrypoints and collect each selected function once."""
        logger.debug("Validate function entrypoint declarations")
        logger.debug("Select unique functions for implementation checks")
        selected_functions: dict[str, spec_model.FunctionTemplate] = {}
        for node in nodes:
            semantics = semantics_by_id[node.node_id]
            function_id = semantics.function_id
            function = spec_definition.functions.get(function_id)
            if function is None or not function.entrypoint:
                raise ValueError(
                    f"Missing entrypoint for function {function_id} "
                    f"used by operator {semantics.operator_id}"
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
        semantics_by_id: dict[str, plan.InvocationSemantics],
    ) -> list[plan.Invocation]:
        """Convert scheduled nodes to portable invocations with resolved metadata."""
        logger.debug("Create portable invocations")
        invocations: list[plan.Invocation] = []
        for node in nodes:
            semantics = semantics_by_id[node.node_id]
            function = selected_functions[semantics.function_id]
            invocations.append(
                plan.Invocation.from_node(
                    spec_definition,
                    node,
                    dependency_ids=[dependency.node_id for dependency in graph.dependencies(node)],
                    return_type=(
                        signatures[semantics.function_id].display.returns
                        if semantics.function_id in signatures
                        else None
                    ),
                    package=packages[function.entrypoint],
                    semantics=semantics,
                )
            )
        return invocations
