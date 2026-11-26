"""Translate concise YAML declarations into Spec document models."""

from __future__ import annotations

import typing

from uptimely.spec import model
from uptimely.spec.python import ref

from . import model as yaml_model


def _resolution(value: typing.Any, *, order: bool = False) -> typing.Any:
    if not isinstance(value, str):
        return value
    dimension, separator, resolution = value.partition(".")
    if not separator or not dimension or not resolution or "." in resolution:
        raise ValueError(f"Expected a dimension.resolution reference, got {value!r}")
    result = {"dimension": dimension, "resolution": resolution}
    if order:
        result["direction"] = "asc"
    return result


class _DocumentAuthoring:
    """Translate a composed YAML document into the shared Spec representation."""

    def __init__(self, source: dict[str, typing.Any]) -> None:
        self.result = dict(source)
        explicit = model.Spec.model_validate(
            {"functions": self.result.get("functions", {})}, context={"log_structure": False}
        ).functions
        self.operator_authoring = yaml_model._OperatorBuilder(explicit)
        self.inferred_dataframes: dict[model.OperatorKey, str] = {}

    def to_document(self) -> dict[str, typing.Any]:
        """Translate compact declarations and infer operator interfaces.

        Returns:
            A Spec document with inferred operator interfaces and function contracts.

        Raises:
            ValueError: A declaration, function reference, or inferred contract is invalid.
        """
        profiles = self.result.get("profiles", {})
        if not isinstance(profiles, dict):
            return self.result
        converted_profiles = {
            profile_id: self._profile(profile_id, profile)
            for profile_id, profile in profiles.items()
        }
        self.result["profiles"] = converted_profiles
        self.result["functions"] = self.operator_authoring.functions.model_dump()
        self._resolve_dataframes()
        return self.result

    def _profile(self, profile_id: str, profile: typing.Any) -> typing.Any:
        if not isinstance(profile, dict):
            return profile
        converted = dict(profile)
        for field in ("grain", "relations", "order"):
            items = converted.get(field)
            if isinstance(items, list):
                converted[field] = [_resolution(item, order=field == "order") for item in items]
        operator_declarations = converted.get("assembly", {})
        if not isinstance(operator_declarations, dict):
            return converted
        features = converted.get("features", {})
        if not isinstance(features, dict):
            raise ValueError(f"profiles.{profile_id}.features must be a mapping")
        features = dict(features)
        produced: list[str] = []
        has_compact_operator = False
        new_operators = {}
        for operator_id, declaration in operator_declarations.items():
            if not isinstance(declaration, dict) or "function" not in declaration:
                new_operators[operator_id] = declaration
                if isinstance(declaration, dict):
                    interface = declaration.get("interface")
                    if isinstance(interface, dict) and isinstance(interface.get("outputs"), list):
                        produced.extend(
                            output.removeprefix("$features.")
                            for output in interface["outputs"]
                            if isinstance(output, str) and output.startswith("$features.")
                        )
                continue
            has_compact_operator = True
            try:
                operator, operator_model, inferred_argument = self.operator_authoring.author(
                    operator_id, declaration
                )
            except (TypeError, ValueError, ImportError, AttributeError) as error:
                raise ValueError(
                    f"profiles.{profile_id}.assembly.{operator_id}: {error}"
                ) from error
            for output in operator.output_ids:
                features.setdefault(output, {})
                produced.append(output)
            new_operators[operator_id] = operator_model.model_dump()
            if inferred_argument is not None:
                self.inferred_dataframes[(profile_id, operator_id)] = inferred_argument
        if has_compact_operator:
            ordered_features = {name: features[name] for name in produced if name in features}
            ordered_features.update(
                (name, value) for name, value in features.items() if name not in ordered_features
            )
            features = ordered_features
        converted["features"] = features
        converted["assembly"] = new_operators
        return converted

    def _resolve_dataframes(self) -> None:
        if not self.inferred_dataframes:
            return
        document = model.Spec.model_validate(self.result, context={"log_structure": False})
        for key, argument in self.inferred_dataframes.items():
            profile_id, operator_id = key
            source_profile = document.input_sources[key]
            if source_profile is None:
                candidates = document.input_candidates[key]
                details = (
                    ", ".join(
                        f"{feature}: {', '.join(owners) if owners else 'no owner'}"
                        for feature, owners in candidates
                    )
                    if candidates
                    else "no non-key input features"
                )
                raise ValueError(
                    f"profiles.{profile_id}.assembly.{operator_id}: Cannot infer dataframe "
                    f"source ({details}). Bind args.{argument} explicitly with a "
                    "profile dataset selector."
                )
            selector = ref.dataset(None if source_profile == profile_id else source_profile).value
            self.result["profiles"][profile_id]["assembly"][operator_id]["compute"]["args"][
                argument
            ] = selector


def to_document(source: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Translate concise YAML declarations into the shared Spec representation.

    Args:
        source: Composed YAML document.

    Returns:
        A Spec document with inferred operator interfaces and function contracts.

    Raises:
        ValueError: A declaration, function reference, or inferred contract is invalid.
    """
    return _DocumentAuthoring(source).to_document()
