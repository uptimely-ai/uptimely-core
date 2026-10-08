"""Specification parser and JSON specification loading helpers."""

import json
from pathlib import Path

from uptimely.compile.entrypoint import read_signature

from ..storage import Storage as SpecificationStorage
from ..validation import validate_dataset_ids, validate_specification
from .bindings import (
    feature_dependencies,
    resolve_binding_args,
)
from .json_functions import python_to_spec_dict
from .json_model import (
    FUNCTION_TYPES,
    Binding,
    Calculation,
    Call,
    Dimension,
    Entity,
    Function,
    FunctionCatalog,
    Specification,
    VectorizeFunction,
)
from .json_serializer import SpecificationSerializer


class SpecificationParser:
    """Parse, resolve, validate, and export a JSON specification."""

    def __init__(self, path: str | Path | None = None):
        """Initialize an empty specification and optionally parse ``path``."""
        self.path: str | None = None
        self.model = Specification()
        self.functions: list[Function] = []
        self.calls: list[Call] = []

        if path is not None:
            self.parse(path)

    @classmethod
    def from_json(cls, path: str | Path) -> Specification:
        """Create a specification from a JSON file."""
        specification = cls()
        return specification.parse(path)

    @classmethod
    def from_python(
        cls,
        datasets: object | None = None,
        functions: object | None = None,
        name: str | None = None,
        dimensions: dict[str, Dimension] | list[Dimension] | None = None,
        *,
        entities: object | None = None,
    ) -> Specification:
        """Create a specification from Python authoring models."""
        specification = cls()
        spec = python_to_spec_dict(
            datasets=datasets,
            functions=functions,
            name=name,
            dimensions=dimensions,
            entities=entities,
        )
        specification._apply_model(Specification.model_validate(spec))
        specification._resolve_functions()
        specification.validate()
        return specification.model

    def to_json(self, path: str | Path) -> str:
        """Write the current specification to disk and return its path."""
        result = SpecificationSerializer.to_json(self.model, path)
        self.path = self.model.path
        return result

    def _apply_model(self, spec: Specification) -> None:
        """Apply a validated specification model."""
        self.model = spec
        self.functions = spec.resolved_functions
        self.calls = spec.calls

    @property
    def version(self) -> str | None:
        """Return the document version."""
        return self.model.version

    @property
    def dimensions(self) -> dict[str, Dimension]:
        """Return the document dimensions."""
        return self.model.dimensions

    @property
    def function_catalog(self) -> FunctionCatalog:
        """Return the declared function catalog."""
        return self.model.functions

    @property
    def entities(self) -> dict[str, Entity]:
        """Return the document entities."""
        return self.model.entities

    def _resolve_functions(self) -> None:
        """Derive resolved functions and calls from bound calculations."""
        functions_by_id: dict[str, Function] = {}
        calls: list[Call] = []

        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets:
                for feature_name, calculation in (
                    dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
                ).items():
                    if calculation.binding is None:
                        continue

                    function_name = calculation.binding.function
                    if function_name not in functions_by_id:
                        template = self.function_catalog.vectorize.get(function_name)
                        if template is None:
                            raise ValueError(f"Unknown vectorize function: {function_name}")
                        functions_by_id[function_name] = self._build_function(
                            function_name, template, calculation
                        )

                    call = self._build_call(
                        function_name,
                        entity_id,
                        feature_name,
                        dataset.id,
                        calculation.binding,
                    )
                    calls.append(call)

                    function = functions_by_id[function_name]
                    calculation.callable = call
                    function.callables.append(call)
                    function.calculations.append(calculation)

        self.model.resolved_functions = list(functions_by_id.values())
        self.model.calls = calls
        self.functions = self.model.resolved_functions
        self.calls = self.model.calls

    @staticmethod
    def _build_function(
        function_name: str,
        template: VectorizeFunction | None,
        calculation: Calculation,
    ) -> Function:
        """Build a deduplicated function entry from its first calculation."""
        return Function(
            id=function_name,
            type="python_function",
            return_type=(
                read_signature(template.entrypoint, Path.cwd()).returns
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
        binding: Binding,
    ) -> Call:
        """Build a call, resolving dependencies and dataset placeholders."""
        if SpecificationParser._contains_dataset_reference(binding.args):
            raise ValueError(
                f"Analytics calculation {feature_name} cannot bind a dataset; "
                "bind its input features or dimensions instead"
            )
        return Call(
            function=function_name,
            entity=entity_id,
            feature=feature_name,
            args=SpecificationParser._replace_arg_placeholders(
                binding.args, dataset_id, feature_name
            ),
            depends_on_features=SpecificationParser._resolve_feature_dependencies(binding.args),
        )

    @staticmethod
    def _contains_dataset_reference(value: object) -> bool:
        """Return whether a binding contains a dataset structural reference."""
        if isinstance(value, str):
            return value.startswith("$datasets.")
        if isinstance(value, dict):
            return any(
                SpecificationParser._contains_dataset_reference(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(SpecificationParser._contains_dataset_reference(item) for item in value)
        return False

    @staticmethod
    def _resolve_feature_dependencies(args: dict | None) -> list[str]:
        """Return unique feature names consumed by a binding."""
        return feature_dependencies(args)

    @staticmethod
    def _replace_arg_placeholders(
        args: dict | None,
        dataset_id: str,
        feature_id: str | None = None,
    ) -> dict:
        """Resolve typed binding references in callable arguments."""
        return resolve_binding_args(args, dataset_id, feature_id)

    def parse(self, path: str | Path | None = None) -> Specification:
        """Load, resolve, and validate a specification from JSON."""
        spec_path = self._spec_path(path)
        spec = self._load_spec(spec_path)
        self.path = spec_path
        self._apply_model(Specification.model_validate(spec))
        self.model.path = spec_path
        self._resolve_functions()
        self.validate()
        return self.model

    @staticmethod
    def _load_spec(path: str | Path) -> dict:
        """Load a single JSON specification file."""
        spec = json.loads(SpecificationStorage.read(path))
        if spec.get("includes", []) or spec.get("external_specs", []):
            raise ValueError("A specification must be defined in a single JSON file")
        return spec

    def validate(
        self,
        functions: list[Function] | None = None,
        calls: list[Call] | None = None,
    ) -> None:
        """Validate that resolved functions and calls define a usable graph."""
        functions = self.functions if functions is None else functions
        calls = self.calls if calls is None else calls
        validate_dataset_ids(self.model)
        seen_function_ids: set[str] = set()
        seen_feature_names: set[str] = set()
        seen_input_names: set[str] = set()
        dataset_of_feature: dict[str, tuple[str, str]] = {}
        dimension_names = set(self.dimensions)

        for entity_id, entity in self.entities.items():
            for dataset in entity.datasets:
                for _, operation in dataset.fragment_operations:
                    for input_name in operation.features:
                        if input_name in dimension_names:
                            continue
                        if input_name in seen_input_names:
                            raise ValueError(f"Duplicate input name: {input_name}")
                        seen_input_names.add(input_name)
                        dataset_of_feature[input_name] = (entity_id, dataset.id)
                for calculation_name in (
                    dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
                ):
                    if calculation_name in seen_feature_names:
                        raise ValueError(f"Duplicate feature name: {calculation_name}")
                    if calculation_name in dimension_names:
                        raise ValueError(
                            f"Feature name duplicates dimension name: {calculation_name}"
                        )
                    if calculation_name in seen_input_names:
                        raise ValueError(f"Feature name duplicates input name: {calculation_name}")
                    seen_feature_names.add(calculation_name)
                    dataset_of_feature[calculation_name] = (entity_id, dataset.id)

        for call in calls:
            owner = dataset_of_feature.get(call.feature)
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
                expected_features = set(
                    dataset.vectorize if hasattr(dataset, "vectorize") else dataset.vectorize
                )
                for sink in dataset.write.values():
                    sink_features = set(self._resolve_feature_dependencies(sink.binding.args))
                    foreign_features = sorted(
                        feature
                        for feature in sink_features
                        if dataset_of_feature.get(feature) != dataset_key
                    )
                    if foreign_features:
                        raise ValueError(
                            f"Sink {sink.id} cannot read features from another dataset: "
                            + ", ".join(foreign_features)
                        )
                    missing_features = sorted(expected_features - sink_features)
                    if missing_features:
                        raise ValueError(
                            f"Sink {sink.id} must bind all analytics features: "
                            + ", ".join(missing_features)
                        )

        for function in functions:
            if not isinstance(function, Function):
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
            if operation_type not in FUNCTION_TYPES:
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
            if not isinstance(call, Call):
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

        validate_specification(self.model, calls)

    def _spec_path(self, path: str | Path | None) -> str:
        """Resolve a supplied path to the JSON specification file."""
        if path is None:
            if self.path is None:
                raise ValueError("A specification path is required")
            return self.path
        target = str(path)
        if SpecificationStorage.is_dir(target):
            candidate = SpecificationStorage.join(target, "spec.json")
            if SpecificationStorage.exists(candidate):
                return candidate
            raise FileNotFoundError(f"No spec.json found in {target}")
        if not SpecificationStorage.exists(target):
            raise FileNotFoundError(target)
        return target


__all__ = ["SpecificationParser"]
