"""Derive vectorize functions and calls from canonical analytics declarations."""

from __future__ import annotations

from . import model, references, resolved


def resolve_functions(
    analytics_definition: model.Analytics,
) -> tuple[list[resolved.Function], list[resolved.Call]]:
    """Resolve vectorize bindings using declarative metadata only."""
    functions_by_id: dict[str, resolved.Function] = {}
    calls: list[resolved.Call] = []
    for entity_id, entity in analytics_definition.entities.items():
        for dataset in entity.datasets:
            for mapping in dataset.mappings.values():
                function_name = mapping.binding.function
                template = analytics_definition.functions.get(function_name)
                if template is None or template.operation != "vectorize":
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
                    functions_by_id[function_name] = _build_function(function_name, template)
                function = functions_by_id[function_name]
                for feature_name in mapping.output_features:
                    feature = dataset.features[feature_name]
                    call = _build_call(
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
    return list(functions_by_id.values()), calls


def _build_function(
    function_name: str,
    template: model.FunctionTemplate,
) -> resolved.Function:
    """Build derived function metadata from its declared template."""
    return resolved.Function(
        id=function_name,
        type="python_function",
        info={"description": template.description},
        entrypoint=template.entrypoint,
        args=list(template.args.values()),
        role="analytics",
    )


def _build_call(
    function_name: str,
    entity_id: str,
    feature_name: str,
    dataset_id: str,
    binding: model.Binding,
    inputs: list[str],
) -> resolved.Call:
    """Build a call with structural references resolved to identifiers."""
    return resolved.Call(
        function=function_name,
        entity=entity_id,
        feature=feature_name,
        args=references.resolve_binding_args(binding.args, dataset_id, feature_name),
        depends_on_features=inputs,
    )
