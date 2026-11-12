"""Expose saved-spec introspection and analytical execution tools."""

import collections
import typing

import fastmcp

from uptimely import engine, entrypoint, project

from . import results, serialization, state


class AnalyticalTools:
    """Implement introspection and execution against a server's saved build."""

    def __init__(self, server_state: state.ServerState) -> None:
        """Bind the analytical tools to one server state.

        Args:
            server_state: Project and saved-build state shared by the tools.
        """
        self._state = server_state

    def register(self, server: fastmcp.FastMCP) -> None:
        """Register analytical tools with an MCP server.

        Args:
            server: MCP server receiving the tool definitions.
        """
        server.tool(self.describe_spec)
        server.tool(self.list_operators)
        server.tool(self.list_functions)
        server.tool(self.describe_function)
        server.tool(self.list_calculated_features)
        server.tool(self.describe_feature)
        server.tool(self.describe_build)
        server.tool(self.execute_build)
        server.tool(self.execute_operator)
        server.tool(self.execute_function)
        server.tool(self.reload_build)

    def describe_spec(self) -> str:
        """Summarize the saved spec, including all declared feature counts.

        Counts cover the saved source model, not just its execution scope.
        Features are profile feature declarations, excluding dimension keys.
        """
        definition = self._state.load_bundle().spec_definition
        return serialization.JsonSerializer.dumps(
            {
                "features": len(definition.features),
                "calculated_features": len(definition.calculated_feature_producers),
                "functions": len(definition.functions.root),
                "operators": len(definition.operators),
                "dimensions": len(definition.dimensions),
                "profiles": {
                    profile_id: {
                        "features": len(profile.features),
                        "operators": len(profile.assembly),
                    }
                    for profile_id, profile in sorted(definition.profiles.items())
                },
            }
        )

    def list_operators(self) -> str:
        """Discover bound operators, their inputs, outputs, and saved availability.

        Use profile and operator IDs with ``execute_operator``. A function can
        have multiple usages with different bound arguments and dependencies.
        """
        bundle = self._state.load_bundle()
        definition = bundle.spec_definition
        available = {
            (invocation.profile_id, invocation.operator_id)
            for invocation in bundle.execution_plan.invocations
        }
        return serialization.JsonSerializer.dumps(
            [
                {
                    "profile": key[0],
                    "operator": key[1],
                    "bindings": {
                        role: binding.function for role, binding in operator.bindings.items()
                    },
                    "input_features": operator.input_features,
                    "output_features": operator.output_features,
                    "execution_form": definition.operator_execution_forms[key],
                    "declared_returns": definition.functions[operator.compute.function].returns,
                    "in_saved_scope": key in available,
                }
                for key, operator in sorted(definition.operator_items)
            ]
        )

    def list_functions(self) -> str:
        """List function ids, categories, and declared return contracts."""
        catalog = self._state.load_bundle().spec_definition.functions
        return serialization.JsonSerializer.dumps(
            [
                {
                    "id": function_id,
                    "category": function.category,
                    "returns": function.returns,
                }
                for function_id, function in sorted(catalog.root.items())
            ]
        )

    def describe_function(self, function_id: str) -> str:
        """Describe a function's contract, bindings, args, and signature.

        Operator usages identify their binding role and derived Spec relationships.

        Args:
            function_id: Function ID from ``list_functions``.

        Raises:
            ValueError: If the function ID is not in the saved catalog.
        """
        definition = self._state.load_bundle().spec_definition
        template = definition.functions.get(function_id)
        if template is None:
            raise ValueError(f"Unknown function: {function_id}")
        signature = (
            entrypoint.Entrypoint(template.entrypoint).function.read_signature()
            if template.validate_signature
            else None
        )
        operator_usages = [
            {
                "profile": key[0],
                "operator": key[1],
                "role": role,
                "execution_form": definition.operator_execution_forms[key],
                "grain_relationships": [
                    {
                        "source_profile": (
                            definition.profiles_by_key[source].id if source is not None else None
                        ),
                        "relationship": relationship,
                    }
                    for source, relationship in definition.operator_grain_relationships[key].items()
                ],
            }
            for key in definition.operators_by_function.get(function_id, [])
            for role, binding in definition.operators_by_key[key].bindings.items()
            if binding.function == function_id
        ]
        return serialization.JsonSerializer.dumps(
            {
                "id": function_id,
                "category": template.category,
                "declared_returns": template.returns,
                "operator_usages": operator_usages,
                "entrypoint": template.entrypoint,
                "python_signature_validation": (
                    "enabled" if template.validate_signature else "disabled"
                ),
                "declared_args": {
                    name: {"type": argument.type, "comment": argument.comment}
                    for name, argument in template.args.items()
                },
                "python_signature": (
                    {"args": signature.args, "returns": signature.returns}
                    if signature is not None
                    else None
                ),
            }
        )

    def list_calculated_features(self) -> str:
        """List calculated feature IDs declared by the saved source model.

        The saved execution scope is reported by ``describe_build``.
        """
        definition = self._state.load_bundle().spec_definition
        return serialization.JsonSerializer.dumps(sorted(definition.calculated_feature_producers))

    def describe_feature(self, feature_id: str) -> str:
        """Show one calculated feature's dependencies.

        Args:
            feature_id: Calculated feature ID from ``list_calculated_features``.

        Returns:
            The producing function, direct dependencies consumed by its binding,
            and the full transitive closure of required calculated and input features.

        Raises:
            ValueError: If the feature is not a calculated feature.
        """
        definition = self._state.load_bundle().spec_definition
        by_feature = definition.calculated_feature_producers
        producer = by_feature.get(feature_id)
        if producer is None:
            raise ValueError(
                f"Unknown calculated feature: {feature_id}. "
                "Use list_calculated_features to see available features."
            )

        profile_id, operator = producer
        transitive: list[str] = []
        queue = list(operator.input_features)
        seen = set(queue)
        while queue:
            current = queue.pop(0)
            transitive.append(current)
            parent_producer = by_feature.get(current)
            if parent_producer is not None:
                for parent in parent_producer[1].input_features:
                    if parent not in seen:
                        seen.add(parent)
                        queue.append(parent)

        return serialization.JsonSerializer.dumps(
            {
                "feature": feature_id,
                "profile": profile_id,
                "function": operator.compute.function,
                "direct_dependencies": operator.input_features,
                "transitive_dependencies": transitive,
                "input_features": [name for name in transitive if name not in by_feature],
                "calculated_dependencies": [name for name in transitive if name in by_feature],
            }
        )

    def describe_build(self) -> str:
        """Report version and execution scope from the validated saved build."""
        bundle = self._state.load_bundle()
        return serialization.JsonSerializer.dumps(self._build_details(bundle))

    def execute_build(self, max_rows: int = 50) -> str:
        """Execute the saved plan as-is and return dimension-keyed calculated rows.

        Args:
            max_rows: Positive maximum number of rows included per dataset.

        Returns:
            Calculated dataset outputs as JSON rows, or engine failures. The
            saved plan's configured sinks also run and may persist output.
        """
        return self._execute(max_rows)

    def execute_operator(self, profile_id: str, operator_id: str, max_rows: int = 50) -> str:
        """Run one bound operator and its prerequisites, returning its analytical outputs.

        Downstream sinks are excluded. Sources and custom prerequisite functions
        can still have side effects. Selecting a sink explicitly executes it.
        Execution uses the saved plan and replaces the project's latest run.

        Args:
            profile_id: Profile ID from ``list_operators``.
            operator_id: Operator ID within the profile.
            max_rows: Positive maximum number of result rows.

        Raises:
            ValueError: If the operator is not in the saved source model.
        """
        definition = self._state.load_bundle().spec_definition
        if (profile_id, operator_id) not in definition.operators_by_key:
            raise ValueError(
                f"Unknown operator: {profile_id}/{operator_id}. "
                "Use list_operators to see available operators."
            )
        return self._execute(max_rows, (profile_id, operator_id))

    def execute_function(
        self,
        function_id: str,
        profile_id: str | None = None,
        operator_id: str | None = None,
        max_rows: int = 50,
    ) -> str:
        """Run a catalog function through its bound operator and dependencies.

        This does not call a raw Python function without its Spec bindings.
        If a function is reused, specify a profile and/or operator to select
        exactly one usage. Compute and merge bindings of that operator run.
        Downstream sinks are excluded unless the selected operator is a sink.
        Execution replaces the project's latest run.

        Args:
            function_id: Function ID from ``list_functions``.
            profile_id: Optional profile to disambiguate function usages.
            operator_id: Optional operator to disambiguate function usages.
            max_rows: Positive maximum number of result rows.

        Raises:
            ValueError: If the function is unknown or has no unique matching usage.
        """
        definition = self._state.load_bundle().spec_definition
        if definition.functions.get(function_id) is None:
            raise ValueError(f"Unknown function: {function_id}")
        usages = sorted(
            {
                key
                for key in definition.operators_by_function.get(function_id, [])
                if (profile_id is None or key[0] == profile_id)
                and (operator_id is None or key[1] == operator_id)
            }
        )
        if not usages:
            raise ValueError(
                f"No matching operator usage for function {function_id}. "
                "Use describe_function or list_operators to see its bindings."
            )
        if len(usages) != 1:
            choices = ", ".join(f"{profile}/{operator}" for profile, operator in usages)
            raise ValueError(
                f"Ambiguous function {function_id}: {choices}. "
                "Specify profile_id and operator_id to select one usage."
            )
        return self._execute(max_rows, usages[0])

    def reload_build(self) -> str:
        """Refresh the validated saved bundle, spec, plan, and recorded scope."""
        bundle = self._state.load_bundle(reload=True)
        definition = bundle.spec_definition
        functions = collections.Counter(
            function.category or "Uncategorized" for function in definition.functions.root.values()
        )
        return serialization.JsonSerializer.dumps(
            {
                **self._build_details(bundle),
                "spec": str(bundle.spec_path),
                "profiles": sorted(definition.profiles),
                "functions": dict(sorted(functions.items())),
            }
        )

    @staticmethod
    def _build_details(bundle: project.BuildBundle) -> dict[str, typing.Any]:
        """Describe saved build scope without implying that it was recompiled."""
        features = bundle.manifest.features
        return {
            "uptimely_version": bundle.manifest.uptimely_version,
            "scope": "all features" if features is None else "selected features",
            "features": features,
        }

    def _execute(self, max_rows: int, operator: tuple[str, str] | None = None) -> str:
        """Execute saved artifacts and serialize dimension-keyed results."""
        if max_rows < 1:
            raise ValueError("max_rows must be a positive integer")
        bundle = self._state.load_bundle()
        runtime = engine.Engine(bundle, self._state.runtime_config())
        result = runtime.run(operator=operator, preview_rows=max_rows)
        payload = {
            **self._build_details(bundle),
            **results.ExecutionResponse.format(bundle, result, operator),
        }
        return serialization.JsonSerializer.dumps(payload)
