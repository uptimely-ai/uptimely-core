"""Analytics parser and JSON specification loading helpers."""

from __future__ import annotations

import json
import pathlib

from uptimely.compile import entrypoint as compile_entrypoint

from .. import storage, validation
from . import bindings, json_functions, json_model, json_serializer


class AnalyticsParser:
    """Parse, resolve, validate, and export a JSON specification."""

    def __init__(self, path: str | pathlib.Path | None = None):
        """Initialize an empty specification and optionally parse ``path``."""
        self.path: str | None = None
        self.model = json_model.Analytics()
        self.functions: list[json_model.Function] = []
        self.calls: list[json_model.Call] = []

        if path is not None:
            self.parse(path)

    @classmethod
    def from_json(cls, path: str | pathlib.Path) -> json_model.Analytics:
        """Create a specification from a JSON file."""
        specification = cls()
        return specification.parse(path)

    @classmethod
    def from_python(
        cls,
        datasets: object | None = None,
        functions: object | None = None,
        name: str | None = None,
        dimensions: dict[str, json_model.Dimension] | list[json_model.Dimension] | None = None,
        *,
        entities: object | None = None,
    ) -> json_model.Analytics:
        """Create a specification from Python authoring models."""
        specification = cls()
        spec = json_functions.python_to_spec_dict(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )
        specification._apply_model(json_model.Analytics.model_validate(spec))
        specification._resolve_functions()
        specification.validate()
        return specification.model

    def to_json(self, path: str | pathlib.Path) -> str:
        """Write the current specification to disk and return its path."""
        result = json_serializer.AnalyticsSerializer.to_json(self.model, path)
        self.path = self.model.path
        return result

    def _apply_model(self, spec: json_model.Analytics) -> None:
        """Apply a validated specification model."""
        self.model = spec
        self.functions = spec.resolved_functions
        self.calls = spec.calls

    @property
    def version(self) -> str | None:
        """Return the document version."""
        return self.model.version

    @property
    def dimensions(self) -> dict[str, json_model.Dimension]:
        """Return the document dimensions."""
        return self.model.dimensions

    @property
    def function_catalog(self) -> json_model.FunctionCatalog:
        """Return the declared function catalog."""
        return self.model.functions

    @property
    def entities(self) -> dict[str, json_model.Entity]:
        """Return the document entities."""
        return self.model.entities

    def _resolve_functions(self) -> None:
        """Derive resolved functions and calls from bound calculations."""
        functions_by_id: dict[str, json_model.Function] = {}
        calls: list[json_model.Call] = []

        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets:
                for mapping in dataset.mappings.values():
                    if mapping.binding.function in self.function_catalog.collapse:
                        continue
                    function_name = mapping.binding.function
                    template = self.function_catalog.vectorize.get(function_name)
                    if template is None:
                        continue
                    if not mapping.output_features:
                        raise ValueError(f"Mapping {mapping.id} must declare one or more features")
                    unknown = set(mapping.output_features) - dataset.features.keys()
                    if unknown:
                        raise ValueError(
                            f"Mapping {mapping.id} references unknown feature: "
                            + ", ".join(sorted(unknown))
                        )
                    if function_name not in functions_by_id:
                        functions_by_id[function_name] = self._build_function(
                            function_name, template, dataset.features[mapping.output_features[0]]
                        )
                    function = functions_by_id[function_name]
                    for feature_name in mapping.output_features:
                        feature = dataset.features[feature_name]
                        call = self._build_call(
                            function_name,
                            entity_id,
                            feature_name,
                            dataset.id,
                            mapping.binding,
                            mapping.input_features,
                        )
                        calls.append(call)
                        function.callables.append(call)
                        function.calculations.append(feature)

        self.model.resolved_functions = list(functions_by_id.values())
        self.model.calls = calls
        self.functions = self.model.resolved_functions
        self.calls = self.model.calls

    @staticmethod
    def _build_function(
        function_name: str,
        template: json_model.VectorizeFunction | None,
        calculation: json_model.Feature,
    ) -> json_model.Function:
        """Build a deduplicated function entry from its first calculation."""
        return json_model.Function(
            id=function_name,
            type="python_function",
            return_type=(
                compile_entrypoint.read_signature(template.entrypoint, pathlib.Path.cwd()).returns
                if template is not None
                else None
            ),
            info={"description": template.description if template else calculation.description},
            entrypoint=template.entrypoint if template else None,
            args=list(template.args.values()) if template else [],
            role="analytics",
        )

    @staticmethod
    def _build_call(
        function_name: str,
        entity_id: str,
        feature_name: str,
        dataset_id: str,
        binding: json_model.Binding,
        inputs: list[str],
    ) -> json_model.Call:
        """Build a call, resolving dependencies and dataset placeholders."""
        return json_model.Call(
            function=function_name,
            entity=entity_id,
            feature=feature_name,
            args=AnalyticsParser._replace_arg_placeholders(binding.args, dataset_id, feature_name),
            depends_on_features=inputs,
        )

    @staticmethod
    def _replace_arg_placeholders(
        args: dict | None,
        dataset_id: str,
        feature_id: str | None = None,
    ) -> dict:
        """Resolve typed binding references in callable arguments."""
        return bindings.resolve_binding_args(args, dataset_id, feature_id)

    def parse(self, path: str | pathlib.Path | None = None) -> json_model.Analytics:
        """Load, resolve, and validate a specification from JSON."""
        spec_path = self._spec_path(path)
        spec = self._load_spec(spec_path)
        self.path = spec_path
        self._apply_model(json_model.Analytics.model_validate(spec))
        self.model.path = spec_path
        self._resolve_functions()
        self.validate()
        return self.model

    @staticmethod
    def _load_spec(path: str | pathlib.Path) -> dict:
        """Load a single JSON specification file."""
        spec = json.loads(storage.Storage.read(path))
        if spec.get("includes", []) or spec.get("external_specs", []):
            raise ValueError("A specification must be defined in a single JSON file")
        return spec

    def validate(
        self,
        functions: list[json_model.Function] | None = None,
        calls: list[json_model.Call] | None = None,
    ) -> None:
        """Validate that resolved functions and calls define a usable graph."""
        functions = self.functions if functions is None else functions
        calls = self.calls if calls is None else calls
        validation.validate_dataset_ids(self.model)
        seen_function_ids: set[str] = set()
        seen_feature_names: set[str] = set()
        dataset_of_feature: dict[str, tuple[str, str]] = {}
        dimension_names = set(self.dimensions)

        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets:
                for feature_name in dataset.features:
                    if feature_name in dimension_names:
                        continue
                    if feature_name in seen_feature_names:
                        raise ValueError(f"Duplicate feature name: {feature_name}")
                    seen_feature_names.add(feature_name)
                    dataset_of_feature[feature_name] = (entity_id, dataset.id)

        for entity in self.entities.values():
            for dataset in entity.datasets:
                for mapping in dataset.mappings.values():
                    if mapping.binding.function in self.function_catalog.collapse:
                        continue
                    if mapping.binding.function in self.function_catalog.vectorize:
                        collisions = sorted(set(mapping.output_features) & dimension_names)
                        if collisions:
                            raise ValueError(
                                "Calculated feature names cannot duplicate entity dimensions: "
                                + ", ".join(collisions)
                            )

        for call in calls:
            owner = dataset_of_feature.get(call.feature)
            if owner is None and call.feature in dimension_names:
                continue
            for dependency in call.depends_on_features:
                dependency_owner = dataset_of_feature.get(dependency)
                if dependency_owner is not None and dependency_owner != owner:
                    raise ValueError(
                        f"Calculation {call.feature} cannot read feature {dependency} "
                        "from another dataset; use a source resource "
                        "operation to transfer features between datasets"
                    )

        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets:
                dataset_key = (entity_id, dataset.id)
                for mapping in dataset.mappings.values():
                    if mapping.binding.function in self.function_catalog.collapse:
                        continue
                    if mapping.binding.function not in self.function_catalog.write:
                        continue
                    sink_features = set(mapping.input_features)
                    foreign_features = sorted(
                        feature
                        for feature in sink_features
                        if feature not in entity.dimension_ids
                        and dataset_of_feature.get(feature) != dataset_key
                    )
                    if foreign_features:
                        raise ValueError(
                            f"Write mapping {mapping.id} cannot read features from "
                            "another dataset: " + ", ".join(foreign_features)
                        )

        for function in functions:
            if not isinstance(function, json_model.Function):
                raise ValueError(
                    f"Function definition must be a Function object, got {type(function).__name__}"
                )

            function_id = function.id
            if not isinstance(function_id, str) or not function_id.strip():
                raise ValueError("Every function must define a non-empty string id")
            if function_id in seen_function_ids:
                raise ValueError(f"Duplicate function id: {function_id}")
            seen_function_ids.add(function_id)

            operation_type = function.type
            if not isinstance(operation_type, str) or not operation_type.strip():
                raise ValueError(f"Function '{function_id}' must define a type")
            if operation_type not in json_model.FUNCTION_TYPES:
                raise ValueError(
                    f"Function '{function_id}' uses unsupported operation type: {operation_type}"
                )

            if operation_type == "python_one_liner":
                entrypoint = function.entrypoint
                if entrypoint and "pl." in entrypoint:
                    raise ValueError(
                        f"Function '{function_id}' python_one_liner entrypoint must not "
                        "reference the polars API directly (pl.col, pl.*); use bare "
                        "variable names or switch to sql_select"
                    )

        seen_output_features: set[str] = set()
        for call in calls:
            if not isinstance(call, json_model.Call):
                raise ValueError(
                    f"Call definition must be a Callable object, got {type(call).__name__}"
                )
            if not isinstance(call.feature, str) or not call.feature.strip():
                raise ValueError("Every call must define a non-empty output feature name")
            if call.feature in seen_output_features:
                raise ValueError(f"Duplicate output feature: {call.feature}")
            seen_output_features.add(call.feature)
            if call.function not in seen_function_ids:
                raise ValueError(
                    f"Call for feature '{call.feature}' references "
                    f"unknown function: {call.function}"
                )

        validation.validate_specification(self.model, calls)

    def _spec_path(self, path: str | pathlib.Path | None) -> str:
        """Resolve a supplied path to the JSON specification file."""
        if path is None:
            if self.path is None:
                raise ValueError("A specification path is required")
            return self.path
        target = str(path)
        if storage.Storage.is_dir(target):
            candidate = storage.Storage.join(target, "spec.json")
            if storage.Storage.exists(candidate):
                return candidate
            raise FileNotFoundError(f"No spec.json found in {target}")
        if not storage.Storage.exists(target):
            raise FileNotFoundError(target)
        return target


__all__ = ["AnalyticsParser"]
