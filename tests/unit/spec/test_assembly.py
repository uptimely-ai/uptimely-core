"""Responsibilities of Python binding and operator declarations."""

import typing

import polars as pl
import pytest

from uptimely.spec import arg_types
from uptimely.spec.python import assembly, feature, functions, ref, row_context


@functions.function(returns="any")
def calculate(value: str) -> str:
    """Calculate a value."""
    return value


def calculate_named_arguments(function: str, arguments: str) -> str:
    """Return values whose names overlap the binding constructor."""
    return function + arguments


def test_binding_and_operator_share_function_metadata_and_conversion() -> None:
    binding = assembly.Bind(calculate, value=ref.feature("source"))
    operator = assembly.Operator(id="calculate", compute=binding)

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


def test_read_and_write_bindings_keep_their_roles_in_python_authoring() -> None:
    read = assembly.Operator(
        id="read",
        read=assembly.Bind(ref.function("reader:read", returns="dataframe")),
    )
    write = assembly.Operator(
        id="write",
        write=assembly.Bind(
            ref.function(
                "writer:write",
                returns="none",
                args={"dataset": arg_types.DATAFRAME},
            ),
            dataset=ref.dataset(),
        ),
    )

    assert read._primary_role == "read"
    assert read.to_model().compute.function == "read"
    assert read.function_catalog()["read"].returns == "dataframe"
    assert write._primary_role == "write"
    assert write.to_model().compute.function == "write"
    assert write.function_catalog()["write"].returns == "none"


def test_read_binding_can_merge_its_returned_fragment() -> None:
    operator = assembly.Operator(
        id="read",
        read=assembly.Bind(ref.function("reader:read", returns="dataframe")),
        merge=assembly.Bind(
            ref.function(
                "merger:merge",
                returns="dataframe",
                args={"dataset": arg_types.DATAFRAME, "fragment": arg_types.DATAFRAME},
            ),
            dataset=ref.dataset(),
            fragment=ref.fragment(),
        ),
    )

    model = operator.to_model()
    assert model.compute.function == "read"
    assert model.merge is not None
    assert list(operator.function_catalog()) == ["read", "merge"]


@pytest.mark.parametrize(
    ("role", "binding", "message"),
    [
        (
            "read",
            assembly.Bind(
                ref.function(
                    "reader:read",
                    returns="dataframe",
                    args={"dataset": arg_types.DATAFRAME},
                ),
                dataset=ref.dataset(),
            ),
            "Read binding must not accept dataframe inputs",
        ),
        (
            "read",
            assembly.Bind(ref.function("reader:read", returns="none")),
            "Read binding must return a dataframe",
        ),
        (
            "write",
            assembly.Bind(
                ref.function("writer:write", returns="none", args={"value": "string"}),
                value="value",
            ),
            "Write binding must accept exactly one dataframe input",
        ),
        (
            "write",
            assembly.Bind(
                ref.function(
                    "writer:write",
                    returns="dataframe",
                    args={"dataset": arg_types.DATAFRAME},
                ),
                dataset=ref.dataset(),
            ),
            "Write binding must return no result",
        ),
    ],
)
def test_read_and_write_bindings_validate_dataframe_contracts(
    role: str, binding: assembly.Bind, message: str
) -> None:
    operator = assembly.Operator(**{role: binding})
    with pytest.raises(ValueError, match=message):
        operator.function_catalog()


def test_binding_accepts_arguments_named_like_constructor_parameters() -> None:
    binding = assembly.Bind(calculate_named_arguments, function="one", arguments="two")

    assert binding.bound_arguments() == {"function": "one", "arguments": "two"}


@pytest.mark.parametrize("arguments", [{}, {"value": "ok", "unexpected": True}])
@pytest.mark.parametrize("method", ["bound_arguments", "to_model", "to_function_template"])
def test_binding_validates_direct_callable_arguments(
    arguments: dict[str, typing.Any], method: str
) -> None:
    binding = assembly.Bind(calculate, **arguments)
    with pytest.raises(TypeError):
        getattr(binding, method)()


def test_deferred_binding_preserves_metadata_without_importing_entrypoint() -> None:
    reference = ref.function(
        "unavailable_assembly_test_package:calculate",
        returns="dataframe",
        args={"value": "string"},
        validate_signature=False,
        description="Deferred calculation.",
    )
    binding = assembly.Bind(
        reference,
        value=1,
    )
    assert binding.reference is reference
    assert binding.bound_arguments() == {"value": 1}
    assert binding.to_model().args["value"].root == 1
    template = binding.to_function_template()
    assert template.entrypoint == reference.entrypoint
    assert template.validate_signature is False
    assert template.description == reference.description


def test_plain_string_binding_conversion_does_not_require_function_semantics() -> None:
    binding = assembly.Bind(
        "unavailable_assembly_test_package:calculate",
    )
    assert binding.to_model().function == "calculate"
    assert not hasattr(binding, "kind")
    with pytest.raises(ValueError, match="Explicit returns metadata is required"):
        binding.to_function_template()


def combine_optional(dataset: pl.DataFrame | None) -> pl.DataFrame:
    return dataset if dataset is not None else pl.DataFrame()


def combine_required(dataset: pl.DataFrame) -> pl.DataFrame:
    return dataset


@pytest.mark.parametrize(
    ("implementation", "expected"),
    [
        (combine_optional, arg_types.OPTIONAL_DATAFRAME),
        (combine_required, arg_types.DATAFRAME),
    ],
)
def test_binding_dataframe_optionality_follows_annotation(
    implementation: typing.Callable[..., object], expected: str
) -> None:
    binding = assembly.Bind(
        implementation,
        dataset=ref.dataset(),
    )
    assert binding.to_function_template().args["dataset"].type == expected


@pytest.mark.parametrize("explicit", [False, True])
def test_operator_owns_input_selection_and_output_exclusion(explicit: bool) -> None:
    operator = assembly.Operator(
        inputs=[] if explicit else None,
        outputs=[feature.Feature(id="result")],
        compute=assembly.Bind(
            "unavailable_assembly_test_package:calculate",
            values=[ref.feature("second"), ref.feature("first"), ref.feature("result")],
        ),
    )
    model = operator.to_model()

    assert model.input_features == ([] if explicit else ["second", "first"])
    assert model.output_features == operator.output_ids == ["result"]


def test_operator_normalizes_explicit_inputs_and_copies_collections() -> None:
    inputs = [feature.Feature(id="first"), ref.feature("second"), "$features.third", "fourth"]
    outputs = [feature.Feature(id="result")]
    operator = assembly.Operator(
        inputs=inputs,
        outputs=outputs,
        compute=assembly.Bind(calculate, value="source"),
    )
    inputs.clear()
    outputs.clear()

    assert operator.to_model().input_features == ["first", "second", "third", "fourth"]
    assert operator.output_ids == ["result"]
    operator.outputs.clear()
    assert operator.output_ids == []


def test_operator_rejects_duplicate_outputs_at_construction() -> None:
    with pytest.raises(ValueError, match="Operator output feature IDs must not repeat"):
        assembly.Operator(
            outputs=[feature.Feature(id="result"), feature.Feature(id="result")],
            compute=assembly.Bind(calculate),
        )


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([ref.feature("source"), "$features.source"], "input feature IDs must not repeat"),
        ([ref.dataset()], "Operator input must reference a feature"),
        (["$features.source.value"], "Invalid operator feature ID"),
        (["@"], "Invalid operator feature ID"),
        ([object()], "Operator inputs must be Feature objects"),
    ],
)
def test_operator_validates_inputs_at_construction(inputs: list[object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        assembly.Operator(inputs=inputs, compute=assembly.Bind(calculate))


def test_operator_validates_mutated_inputs_again_when_converted() -> None:
    operator = assembly.Operator(
        inputs=["source"],
        compute=assembly.Bind(
            "unavailable_assembly_test_package:calculate",
        ),
    )
    operator.inputs.append("$features.source")

    with pytest.raises(ValueError, match="input feature IDs must not repeat"):
        operator.to_model()


@pytest.mark.parametrize(
    ("outputs", "error", "message"),
    [
        ("result", TypeError, "outputs must be a sequence"),
        ([object()], TypeError, "outputs must contain Features"),
        ([feature.Feature(id="value.name")], ValueError, "Invalid operator feature ID"),
    ],
)
def test_operator_validates_outputs_at_construction(
    outputs: object, error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        assembly.Operator(outputs=outputs, compute=assembly.Bind(calculate))


def test_operator_combines_binding_contracts_but_only_stage_row_context() -> None:
    stage = assembly.Bind(
        ref.function("unavailable_assembly_test_package:calculate", returns="dataframe"),
        value=row_context.rows(ref.feature("source"), before=2),
    )
    merge = assembly.Bind(
        ref.function(
            "unavailable_assembly_test_package:combine",
            returns="dataframe",
            args={"dataset": "dataframe", "fragment": "dataframe"},
        ),
        dataset=row_context.rows(ref.dataset(), before=9),
        fragment=ref.fragment(),
    )
    operator = assembly.Operator(
        id="calculate",
        stage=stage,
        merge=merge,
        row_context=row_context.rows("explicit", after=3),
    )
    model = operator.to_model()
    assert model.compute == stage.to_model()
    assert model.merge == merge.to_model()
    assert model.row_context == row_context.rows("expected", before=2, after=3).row_context
    assert list(operator.function_catalog()) == ["calculate", "combine"]
    assert operator.function_catalog()["combine"] == merge.to_function_template()


def test_operator_rejects_merge_with_wrong_dataframe_arity() -> None:
    operator = assembly.Operator(
        id="calculate",
        stage=assembly.Bind(
            ref.function("unavailable_assembly_test_package:calculate", returns="dataframe"),
        ),
        merge=assembly.Bind(
            ref.function(
                "unavailable_assembly_test_package:combine",
                returns="dataframe",
                args={"dataset": "dataframe"},
            ),
            dataset=ref.dataset(),
        ),
    )
    with pytest.raises(ValueError, match="invalid dataframe arity: 1"):
        operator.function_catalog()


@pytest.mark.parametrize(
    ("read", "compute", "write", "stage", "merge"),
    [
        (False, False, False, False, False),
        (False, False, False, True, False),
        (False, False, False, False, True),
        (False, True, False, False, True),
        (True, True, False, False, False),
        (True, False, True, False, False),
        (False, False, True, False, True),
    ],
)
def test_operator_requires_one_supported_binding_form(
    read: bool, compute: bool, write: bool, stage: bool, merge: bool
) -> None:
    dataframe_binding = assembly.Bind(ref.function("example:work", returns="dataframe"))
    no_result_binding = assembly.Bind(ref.function("example:write", returns="none"))
    with pytest.raises(ValueError, match="one primary binding"):
        assembly.Operator(
            read=dataframe_binding if read else None,
            compute=dataframe_binding if compute else None,
            write=no_result_binding if write else None,
            stage=dataframe_binding if stage else None,
            merge=no_result_binding if merge else None,
        )


def test_stage_requires_dataframe_result() -> None:
    operator = assembly.Operator(
        stage=assembly.Bind(ref.function("example:work", returns="none")),
        merge=assembly.Bind(
            ref.function(
                "example:merge",
                returns="dataframe",
                args={"dataset": "dataframe", "fragment": "dataframe"},
            ),
            dataset=ref.dataset(),
            fragment=ref.fragment(),
        ),
    )
    with pytest.raises(ValueError, match="stage binding must return a dataframe"):
        operator.function_catalog()
