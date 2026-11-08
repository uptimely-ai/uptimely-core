"""Responsibilities of Python binding, interface, and operator declarations."""

import typing

import pytest

from uptimely.spec import arg_types
from uptimely.spec.python import assembly, feature, functions, ref, row_context


@functions.function(kind="vectorize")
def calculate(value: str) -> str:
    """Calculate a value."""
    return value


def test_binding_and_operator_share_function_metadata_and_conversion() -> None:
    binding = assembly.Binding(function=calculate, arguments={"value": ref.feature("source")})
    operator = assembly.Operator(id="calculate", interface=assembly.Interface(), compute=binding)

    assert binding.kind == operator.kind == "vectorize"
    assert binding.reference == operator.reference == ref.function(calculate)
    assert operator.catalog_id == binding.reference.name
    assert binding.bound_arguments() == operator.bound_arguments() == binding.arguments
    assert binding.bound_arguments() is not binding.arguments
    assert binding.to_model() == operator.to_model().compute
    template = binding.to_function_template()
    assert operator.function_catalog()["calculate"] == template
    assert template.description == "Calculate a value."
    assert template.entrypoint == binding.reference.entrypoint
    assert template.args["value"].type == arg_types.STRING


@pytest.mark.parametrize("arguments", [{}, {"value": "ok", "unexpected": True}])
@pytest.mark.parametrize("method", ["bound_arguments", "to_model", "to_function_template"])
def test_binding_validates_direct_callable_arguments(
    arguments: dict[str, typing.Any], method: str
) -> None:
    binding = assembly.Binding(function=calculate, arguments=arguments)
    with pytest.raises(TypeError):
        getattr(binding, method)()


def test_deferred_binding_preserves_metadata_without_importing_entrypoint() -> None:
    reference = ref.function(
        "unavailable_assembly_test_package:calculate",
        kind="vectorize",
        validate_signature=False,
        description="Deferred calculation.",
    )
    binding = assembly.Binding(function=reference, arguments={"value": 1})
    assert binding.reference is reference
    assert binding.kind == "vectorize"
    assert binding.bound_arguments() == {"value": 1}
    assert binding.to_model().args["value"].root == 1
    template = binding.to_function_template()
    assert template.entrypoint == reference.entrypoint
    assert template.validate_signature is False
    assert template.description == reference.description


def test_plain_string_binding_conversion_does_not_require_function_semantics() -> None:
    binding = assembly.Binding(function="unavailable_assembly_test_package:calculate")
    assert binding.to_model().function == "calculate"
    with pytest.raises(ValueError, match="Function kind is required"):
        _ = binding.kind
    with pytest.raises(ValueError, match="Function kind is required"):
        binding.to_function_template()


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("merge", arg_types.OPTIONAL_DATAFRAME), ("collapse", arg_types.DATAFRAME)],
)
def test_binding_target_optionality_depends_on_function_kind(
    kind: typing.Any, expected: str
) -> None:
    binding = assembly.Binding(
        function=ref.function("unavailable_assembly_test_package:combine", kind=kind),
        arguments={"target": ref.dataset()},
    )
    assert binding.to_function_template().args["target"].type == expected


@pytest.mark.parametrize("explicit", [False, True])
def test_interface_owns_input_selection_and_output_exclusion(explicit: bool) -> None:
    compute = assembly.Binding(
        function="unavailable_assembly_test_package:calculate",
        arguments={"values": [ref.feature("second"), ref.feature("first"), ref.feature("result")]},
    ).to_model()
    merge = assembly.Binding(
        function="unavailable_assembly_test_package:combine",
        arguments={"values": [ref.feature("first"), ref.feature("third")]},
    ).to_model()
    interface = assembly.Interface(
        inputs=[] if explicit else None, outputs=[feature.Feature(id="result")]
    )

    model = interface.to_model(compute=compute, merge=merge)
    assert model.input_ids == ([] if explicit else ["second", "first", "third"])
    assert model.output_ids == interface.output_ids == ["result"]


def test_interface_normalizes_explicit_inputs_and_copies_collections() -> None:
    inputs = [feature.Feature(id="first"), ref.feature("second"), "$features.third", "fourth"]
    outputs = [feature.Feature(id="result")]
    interface = assembly.Interface(inputs=inputs, outputs=outputs)
    inputs.clear()
    outputs.clear()

    compute = assembly.Binding(function="unavailable_assembly_test_package:calculate").to_model()
    assert interface.to_model(compute=compute).input_ids == ["first", "second", "third", "fourth"]
    assert interface.output_ids == ["result"]
    interface.outputs.clear()
    assert interface.output_ids == []


def test_interface_rejects_duplicate_outputs_at_construction() -> None:
    with pytest.raises(ValueError, match="Operator output feature IDs must not repeat"):
        assembly.Interface(outputs=[feature.Feature(id="result"), feature.Feature(id="result")])


def test_interface_rejects_non_feature_input_references() -> None:
    with pytest.raises(ValueError, match="Operator input must reference a feature"):
        assembly.Interface(inputs=[ref.dataset()])


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([ref.feature("source"), "$features.source"], "input feature IDs must not repeat"),
        (["$features.source.value"], "Invalid operator feature ID"),
        (["@"], "Invalid operator feature ID"),
        ([object()], "Operator inputs must be Feature objects"),
    ],
)
def test_interface_validates_inputs_at_construction(inputs: list[object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        assembly.Interface(inputs=inputs)


def test_interface_validates_mutated_inputs_again_when_converted() -> None:
    inputs = ["source"]
    interface = assembly.Interface(inputs=inputs)
    interface.inputs.append("$features.source")
    compute = assembly.Binding(function="unavailable_assembly_test_package:calculate").to_model()

    with pytest.raises(ValueError, match="input feature IDs must not repeat"):
        interface.to_model(compute=compute)


@pytest.mark.parametrize(
    ("outputs", "error", "message"),
    [
        ("result", TypeError, "outputs must be a sequence"),
        ([object()], TypeError, "outputs must contain Features"),
        ([feature.Feature(id="value.name")], ValueError, "Invalid operator feature ID"),
    ],
)
def test_interface_validates_outputs_at_construction(
    outputs: object, error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        assembly.Interface(outputs=outputs)


def test_operator_combines_binding_contracts_but_only_compute_row_context() -> None:
    compute = assembly.Binding(
        function=ref.function("unavailable_assembly_test_package:calculate", kind="collapse"),
        arguments={"value": row_context.rows(ref.feature("source"), before=2)},
    )
    merge = assembly.Binding(
        function=ref.function("unavailable_assembly_test_package:combine", kind="merge"),
        arguments={"target": row_context.rows(ref.dataset(), before=9)},
    )
    operator = assembly.Operator(
        id="calculate",
        interface=assembly.Interface(),
        compute=compute,
        merge=merge,
        row_context=row_context.rows("explicit", after=3),
    )
    model = operator.to_model()
    assert model.compute == compute.to_model()
    assert model.merge == merge.to_model()
    assert model.row_context == row_context.rows("expected", before=2, after=3).row_context
    assert list(operator.function_catalog()) == ["calculate", "combine"]
    assert operator.function_catalog()["combine"] == merge.to_function_template()


@pytest.mark.parametrize(
    "function",
    ["unavailable_assembly_test_package:combine", ref.function(calculate)],
)
def test_operator_preserves_invalid_merge_contract_error(
    function: str | ref.FunctionReference,
) -> None:
    with pytest.raises(ValueError, match="merge binding must reference a function of kind 'merge'"):
        assembly.Operator(
            id="calculate",
            interface=assembly.Interface(),
            compute=assembly.Binding(
                function=ref.function(
                    "unavailable_assembly_test_package:calculate", kind="collapse"
                )
            ),
            merge=assembly.Binding(function=function),
        )
