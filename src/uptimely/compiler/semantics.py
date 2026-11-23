"""Derive analytical invocation semantics from a validated Spec."""

from __future__ import annotations

from uptimely import plan, spec
from uptimely.spec import arg_types
from uptimely.spec.model import profile as profile_module
from uptimely.spec.model import spec as spec_module


class InvocationSemanticsBuilder:
    """Derive invocation contracts for an operator's bindings."""

    @classmethod
    def build(
        cls, spec_definition: spec.Spec, key: spec_module.OperatorKey, operator: spec.Operator
    ) -> dict[profile_module.OperatorBindingRole.Value, plan.InvocationSemantics]:
        """Derive semantic contracts for one operator.

        Args:
            spec_definition: The validated Spec containing the operator.
            key: The operator's profile and declaration keys.
            operator: The operator to expand.

        Returns:
            Invocation contracts keyed by binding role.
        """
        profile_id = spec_definition.profiles_by_key[key[0]].id
        relationships = operator.grain_relationships(spec_definition, key)
        return {
            role: cls._create_semantics(
                spec_definition, key, operator, binding, role, profile_id, relationships
            )
            for role, binding in operator.bindings.items()
        }

    @staticmethod
    def _create_semantics(
        spec_definition: spec.Spec,
        key: spec_module.OperatorKey,
        operator: spec.Operator,
        binding: spec.Binding,
        role: profile_module.OperatorBindingRole.Value,
        profile_id: str,
        relationships: dict[spec_module.ProfileKey | None, profile_module.GrainRelationship.Value],
    ) -> plan.InvocationSemantics:
        """Derive one invocation contract from its operator and function declarations."""
        function = spec_definition.functions[binding.function]
        is_compute = role == profile_module.OperatorBindingRole.COMPUTE
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
        if role == profile_module.OperatorBindingRole.MERGE:
            result = plan.InvocationResultKind.TARGET
        elif function.returns != arg_types.DATAFRAME:
            result = plan.InvocationResultKind.NONE
        elif operator.merge is not None:
            result = plan.InvocationResultKind.FRAGMENT
        else:
            result = plan.InvocationResultKind.TARGET

        profile_key = spec_definition.profile_keys[profile_id]
        profile = spec_definition.profiles[profile_id]
        key_types = spec_definition.key_types_by_profile[profile_key]
        column_types = (
            {
                feature_id: feature.type
                for feature_id, feature in profile.features.items()
                if feature.type is not None
            }
            | spec_definition.identifier_types_by_profile[profile_key]
            | key_types
        )
        output_features = operator.output_features if is_compute else []

        return plan.InvocationSemantics(
            role=role,
            result=result,
            produces_features=contract.produces_features if is_compute else False,
            is_sink=(contract.is_sink or operator.is_workflow) if is_compute else False,
            is_workflow=operator.is_workflow if is_compute else False,
            is_seed=is_compute and profile.seed == operator.id,
            dataframe_input_scope=(
                contract.dataframe_input_scope
                if is_compute
                else profile_module.DataFrameInputScope.UNRESTRICTED
            ),
            fragment_dimensions=(
                contract.fragment_dimensions
                if is_compute
                else profile_module.FragmentDimensions.NOT_APPLICABLE
            ),
            row_count_relation=(
                contract.row_count_relation
                if is_compute
                else profile_module.RowCountRelation.UNRESTRICTED
            ),
            key_relation=(
                contract.key_relation if is_compute else profile_module.KeyRelation.UNRESTRICTED
            ),
            row_order_relation=(
                contract.row_order_relation
                if is_compute
                else profile_module.RowOrderRelation.UNRESTRICTED
            ),
            existing_data_relation=(
                contract.existing_data_relation
                if is_compute
                else profile_module.ExistingDataRelation.UNRESTRICTED
            ),
            function_id=binding.function,
            operator_id=operator.id,
            profile_id=profile_id,
            output_features=list(output_features),
            input_features=list(operator.input_features) if is_compute else [],
            row_context=operator.row_context if is_compute else None,
            target_identifiers=list(spec_definition.identifiers_by_profile[profile_key]),
            fragment_keys=list(key_types),
            output_types={
                feature_id: column_types.get(feature_id) for feature_id in output_features
            },
            column_types=column_types,
            argument_types={
                argument_name: argument.type for argument_name, argument in function.args.items()
            },
        )
