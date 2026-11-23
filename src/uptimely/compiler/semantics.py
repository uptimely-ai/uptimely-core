"""Derive analytical invocation semantics from a validated Spec."""

from __future__ import annotations

from uptimely import plan, spec
from uptimely.spec import arg_types

from . import graph as graph_module


class InvocationSemanticsBuilder:
    """Resolve Spec operators into graph nodes and invocation semantics."""

    @staticmethod
    def create_nodes(
        spec_definition: spec.Spec,
    ) -> tuple[list[graph_module.InvocationNode], dict[str, plan.InvocationSemantics]]:
        """Expand Spec operators and derive one semantic contract per invocation."""
        invocations: list[graph_module.InvocationNode] = []
        semantics_by_id: dict[str, plan.InvocationSemantics] = {}

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

                node = graph_module.InvocationNode(
                    function_id=binding.function,
                    profile_id=profile_id,
                    operator_id=operator.id,
                    role=role,
                    arguments=binding.args,
                )
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
                invocations.append(node)
                semantics_by_id[node.node_id] = semantics

        nodes_by_id: dict[str, graph_module.InvocationNode] = {}
        for invocation in invocations:
            previous = nodes_by_id.get(invocation.node_id)
            if previous is not None:
                raise ValueError(
                    f"Invocation ID collision {invocation.node_id!r} between operators "
                    f"{previous.profile_id!r}/{previous.operator_id!r} "
                    f"({previous.role}:{previous.function_id}) and "
                    f"{invocation.profile_id!r}/{invocation.operator_id!r} "
                    f"({invocation.role}:{invocation.function_id})"
                )
            nodes_by_id[invocation.node_id] = invocation

        return invocations, semantics_by_id
