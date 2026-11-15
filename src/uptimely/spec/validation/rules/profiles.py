"""Atomic profile grain checks."""

import logging

from uptimely.spec import arg_types, operator_kinds
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors

logger = logging.getLogger(__name__)


def validate_seeds(spec: spec_model.Spec) -> None:
    """Require each seed to initialize its profile with a complete dataframe."""
    logger.debug("Check profile seed operators initialize their target datasets")
    for profile_id, profile in spec.profile_items:
        if profile.seed is None:
            continue
        path = ("profiles", profile_id, "seed")
        seed = profile.assembly.get(profile.seed)
        if not profile.seed.strip() or seed is None:
            raise errors.SpecError(
                f"Profile {profile_id} seed must reference an operator in its assembly",
                code="invalid_profile_seed",
                path=path,
            )
        if seed.merge is not None:
            raise errors.SpecError(
                f"Profile {profile_id} seed must not have a merge",
                code="invalid_profile_seed",
                path=path,
            )
        function = spec.functions.root.get(seed.compute.function)
        if function is None or function.returns != "dataframe":
            raise errors.SpecError(
                f"Profile {profile_id} seed must return a dataframe",
                code="invalid_profile_seed",
                path=path,
            )
        dataframe_arguments = [
            (argument, seed.compute.args.get(name))
            for name, argument in function.args.items()
            if arg_types.is_dataframe(argument.type)
        ]
        if any(
            value is not None and value.profile_id(profile_id) == profile_id
            for _, value in dataframe_arguments
        ):
            raise errors.SpecError(
                f"Profile {profile_id} seed cannot consume its own target dataframe",
                code="invalid_profile_seed",
                path=path,
            )
        if any(
            argument.type == arg_types.OPTIONAL_DATAFRAME for argument, _ in dataframe_arguments
        ):
            raise errors.SpecError(
                f"Profile {profile_id} seed dataframe input must not be nullable",
                code="invalid_profile_seed",
                path=path,
            )
        for operator_id, operator in profile.assembly.items():
            if operator_id == profile.seed or operator.merge is not None:
                continue
            other_key = (profile_id, operator_id)
            kind = operator_kinds.OPERATOR_KINDS[spec.operator_kinds[other_key]]
            if kind.is_source:
                raise errors.SpecError(
                    f"Profile {profile_id} operator {operator_id} must merge its result "
                    "instead of replacing the seed",
                    code="invalid_profile_seed",
                    path=("profiles", profile_id, "assembly", operator_id),
                )


def validate_relations(spec: spec_model.Spec) -> None:
    """Require distinct, valid relations outside the profile grain and features."""
    logger.debug("Check spec profile relations reference distinct non-grain columns")
    for profile_id, profile in spec.profile_items:
        seen = set(spec.identifiers_by_profile[profile_id])
        for index, reference in enumerate(profile.relations):
            path = ("profiles", profile_id, "relations", index)
            dimension = spec.dimensions.get(reference.dimension)
            if dimension is None:
                raise errors.SpecError(
                    f"Profile {profile_id} relation references unknown dimension: "
                    f"{reference.dimension}",
                    code="unknown_relation_dimension",
                    path=(*path, "dimension"),
                )
            resolution = dimension.resolutions.get(reference.resolution)
            if resolution is None:
                raise errors.SpecError(
                    f"Profile {profile_id} relation references unknown resolution: "
                    f"{reference.resolution}",
                    code="unknown_relation_resolution",
                    path=(*path, "resolution"),
                )
            if resolution.key in seen:
                raise errors.SpecError(
                    f"Profile {profile_id} relation repeats column: {resolution.key}",
                    code="duplicate_relation_column",
                    path=(*path, "resolution"),
                )
            if resolution.key in profile.features:
                raise errors.SpecError(
                    f"Profile {profile_id} relation column is also declared as a feature: "
                    f"{resolution.key}",
                    code="relation_feature_collision",
                    path=(*path, "resolution"),
                )
            seen.add(resolution.key)


def validate_grain_dimensions(spec: spec_model.Spec) -> None:
    """Require profile grain references to name declared dimensions."""
    logger.debug("Check spec profile grains reference declared dimensions")
    for profile_id, profile in spec.profile_items:
        for index, reference in enumerate(profile.grain):
            logger.debug(
                "Check grain dimension %s for spec profile %s",
                reference.dimension,
                profile_id,
            )
            if reference.dimension not in spec.dimensions:
                raise errors.SpecError(
                    f"Profile {profile_id} grain references unknown dimension: "
                    f"{reference.dimension}",
                    code="unknown_grain_dimension",
                    path=("profiles", profile_id, "grain", index, "dimension"),
                )


def validate_unique_grain_dimensions(spec: spec_model.Spec) -> None:
    """Require each profile grain to select at most one resolution per dimension."""
    logger.debug("Check spec profile grains select each dimension at most once")
    for profile_id, profile in spec.profile_items:
        logger.debug("Check grain dimension uniqueness for spec profile %s", profile_id)
        seen: set[str] = set()
        for index, reference in enumerate(profile.grain):
            if reference.dimension in seen:
                raise errors.SpecError(
                    f"Profile {profile_id} grain repeats dimension: {reference.dimension}",
                    code="duplicate_grain_dimension",
                    path=("profiles", profile_id, "grain", index, "dimension"),
                )
            seen.add(reference.dimension)


def validate_grain_resolutions(spec: spec_model.Spec) -> None:
    """Require profile grain references to name resolutions of their dimensions."""
    logger.debug("Check spec profile grains reference resolutions of their dimensions")
    for profile_id, profile in spec.profile_items:
        for index, reference in enumerate(profile.grain):
            logger.debug(
                "Check grain resolution %s in dimension %s for spec profile %s",
                reference.resolution,
                reference.dimension,
                profile_id,
            )
            dimension = spec.dimensions[reference.dimension]
            if reference.resolution not in dimension.resolutions:
                raise errors.SpecError(
                    f"Profile {profile_id} grain references unknown resolution "
                    f"{reference.resolution} for dimension {reference.dimension}",
                    code="unknown_grain_resolution",
                    path=("profiles", profile_id, "grain", index, "resolution"),
                )


def validate_unique_grain_keys(spec: spec_model.Spec) -> None:
    """Require profile grain resolutions to use distinct dataframe key columns."""
    logger.debug("Check spec profile grains use distinct dataframe key columns")
    for profile_id, profile in spec.profile_items:
        logger.debug("Check grain dataframe-key uniqueness for spec profile %s", profile_id)
        seen: set[str] = set()
        for index, reference in enumerate(profile.grain):
            dimension = spec.dimensions[reference.dimension]
            resolution = dimension.resolutions[reference.resolution]
            if resolution.key in seen:
                raise errors.SpecError(
                    f"Profile {profile_id} grain repeats dataframe key: {resolution.key}",
                    code="duplicate_grain_key",
                    path=("profiles", profile_id, "grain", index, "resolution"),
                )
            seen.add(resolution.key)
