"""Atomic action input, reference, and source scope checks."""

from uptimely.spec import functions, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors


def validate_source_feature(spec: spec_model.Spec) -> None:
    """Require collapse to reference a source feature."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is not None
            and function.kind == functions.COLLAPSE
            and not (spec.input_candidates[key])
        ):
            raise ValueError(f"Collapse {action.id} must reference a source feature")


def validate_feature_owner(spec: spec_model.Spec) -> None:
    """Require a collapse source feature to have exactly one owner."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind != functions.COLLAPSE:
            continue
        for feature, owners in spec.input_candidates[key]:
            if not owners:
                raise ValueError(
                    f"Collapse {action.id} references unknown input feature: {feature}"
                )
            if len(owners) != 1:
                raise ValueError(f"Collapse {action.id} has ambiguous input feature: {feature}")


def validate_source_count(spec: spec_model.Spec) -> None:
    """Require all collapse source features to belong to one dataset."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind != functions.COLLAPSE:
            continue
        source_ids = {owners[0][1] for _, owners in spec.input_candidates[key] if len(owners) == 1}
        if len(source_ids) != 1:
            raise ValueError(
                f"Collapse {action.id} input features must belong to one "
                "dataset; use expand to combine inputs from different datasets"
            )


def validate_source_target(spec: spec_model.Spec) -> None:
    """Reject the target dataset as a collapse source."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        source = spec.input_sources[key]
        if (
            function is not None
            and function.kind == functions.COLLAPSE
            and (source is not None and source[1] == key[1])
        ):
            raise ValueError(f"Collapse {action.id} cannot use its target dataset as source")


def validate_grouping_dimensions(spec: spec_model.Spec) -> None:
    """Require grouping dimensions to exist in the collapse source."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind != functions.COLLAPSE:
            continue
        source = spec.input_sources[key]
        if source is not None and not (
            spec.dimensions_by_dataset[key[:2]] <= spec.dimensions_by_dataset[source]
        ):
            raise ValueError(
                f"Collapse {action.id} grouping dimensions must exist in source {source[1]}"
            )


def validate_source_features(spec: spec_model.Spec) -> None:
    """Require collapse input features to belong to its source."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind != functions.COLLAPSE:
            continue
        source = spec.input_sources[key]
        if source is not None:
            unknown = sorted(set(action.input_features) - spec.local_features[source])
            if unknown:
                raise ValueError(
                    f"Collapse {action.id} references features outside source "
                    f"{source[1]}: " + ", ".join(unknown)
                )


def validate_source_dimensions(spec: spec_model.Spec) -> None:
    """Require structural dimension references to belong to the source."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if function is None or function.kind != functions.COLLAPSE:
            continue
        source = spec.input_sources[key]
        referenced = set(action.dimensions_references)
        unknown = sorted(
            (referenced & spec.dimensions.keys())
            - (spec.dimensions_by_dataset[source] if source is not None else frozenset())
        )
        if unknown:
            raise ValueError(
                f"Collapse {action.id} references unknown source dimensions: " + ", ".join(unknown)
            )


def validate_input_feature(spec: spec_model.Spec) -> None:
    """Require an explicit input feature to be declared."""
    feature_names = spec.dimensions.keys() | spec.feature_owners.keys()
    for action in spec.actions:
        for feature in action.input_features:
            if feature not in feature_names:
                raise ValueError(f"Action {action.id} references unknown input feature: {feature}")


def validate_input_scope(spec: spec_model.Spec) -> None:
    """Require target-scoped function inputs to belong to the target dataset."""
    for key, action in spec.action_items:
        function = spec.functions.root.get(action.binding.function)
        if (
            function is None
            or functions.FUNCTION_KINDS[function.kind].feature_input_scope != "target"
        ):
            continue
        for feature in action.input_features:
            if feature not in spec.local_features[key[:2]]:
                raise ValueError(
                    f"Action {action.id} cannot read feature {feature} from another dataset"
                )


def validate_feature_reference(spec: spec_model.Spec) -> None:
    """Require a structural feature reference to be declared."""
    feature_names = spec.dimensions.keys() | spec.feature_owners.keys()
    for action in spec.actions:
        for feature in action.feature_selectors:
            if feature != selectors.CURRENT_ID and feature not in feature_names:
                raise ValueError(f"Action {action.id} references unknown feature: {feature}")


def validate_dataset_reference(spec: spec_model.Spec) -> None:
    """Require a structural dataset reference to be declared."""
    for action in spec.actions:
        for dataset in action.dataset_references:
            if dataset != selectors.CURRENT_ID and dataset not in spec.datasets:
                raise ValueError(f"Action {action.id} references unknown dataset: {dataset}")


def validate_dimension_reference(spec: spec_model.Spec) -> None:
    """Require a structural dimension reference to be declared."""
    for key, action in spec.action_items:
        for dimension, path in action.dimension_reference_paths:
            if dimension not in spec.dimensions:
                raise errors.SpecError(
                    f"Action {action.id} references unknown dimension: {dimension}",
                    code="unknown_dimension_reference",
                    path=(*spec.declaration_paths[key], "binding", "args", *path),
                )
