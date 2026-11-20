"""Reusable callable contracts and signature validation."""

import importlib
from collections.abc import Callable

import polars as pl
import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import python as authoring
from uptimely.spec.python import functions, ref


def dataframe(value: pl.DataFrame) -> pl.DataFrame:
    return value


def lazyframe(value: pl.LazyFrame) -> pl.LazyFrame:
    return value


def no_result(value: str) -> None:
    del value


def scalar_result(value: str) -> str:
    return value


def opaque_result(value: str) -> object:
    return value


def maybe_dataframe(value: pl.DataFrame | None) -> pl.DataFrame:
    return value if value is not None else pl.DataFrame()


def args_callable(value: str) -> str:
    return value


@authoring.function(returns="dataframe")
def explicit_result(value: str) -> str:
    return value


def test_decorator_preserves_callable_identity_and_has_no_operator_kind() -> None:
    def original(value: str) -> str:
        return value

    result = functions.function(returns="any", args={"value": "string"})(original)

    assert result is original
    assert result("value") == "value"
    assert functions.declared_metadata(result).returns == "any"
    assert not hasattr(functions.declared_metadata(result), "kind")


def test_public_decorator_and_module_exports_are_unambiguous() -> None:
    module = importlib.import_module("uptimely.spec.python.functions")
    assert authoring.functions is module
    assert authoring.function is module.function
    assert not hasattr(authoring, "kind")
    assert not hasattr(authoring.assembly, "kind")


@pytest.mark.parametrize(
    ("implementation", "expected"),
    [(dataframe, "dataframe"), (lazyframe, "dataframe"), (no_result, "none")],
)
def test_return_role_is_inferred_from_unambiguous_annotations(
    implementation: Callable[..., object], expected: str
) -> None:
    assert ref.function(implementation).returns == expected


@pytest.mark.parametrize("implementation", [scalar_result, opaque_result])
def test_ambiguous_return_annotations_require_explicit_role_when_bound(
    implementation: Callable[..., object],
) -> None:
    reference = ref.function(implementation)
    assert reference.returns is None

    operator = authoring.Operator(
        id="calculate",
        outputs=[],
        compute=authoring.Bind(
            reference,
            value="sample",
        ),
    )
    with pytest.raises(ValueError, match="Explicit returns metadata is required"):
        operator.function_catalog()


def test_explicit_return_role_is_checked_against_annotation() -> None:
    assert ref.function(scalar_result, returns="any").returns == "any"
    with pytest.raises(ValueError, match="contradicts return annotation"):
        ref.function(scalar_result, returns="dataframe")


def test_reference_captures_signature_and_checks_argument_names_at_authoring() -> None:
    reference = ref.function(dataframe)
    assert reference.signature is not None
    assert tuple(reference.signature.parameters) == ("value",)

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        authoring.Bind(
            reference,
            value=pl.DataFrame(),
            other=pl.DataFrame(),
        ).to_model()
    with pytest.raises(TypeError, match="missing a required argument"):
        authoring.Bind(
            reference,
        ).to_model()


def test_direct_callable_and_callable_reference_share_the_same_contract() -> None:
    direct = authoring.Bind(
        dataframe,
        value=pl.DataFrame(),
    )
    reference = authoring.Bind(
        ref.function(dataframe),
        value=pl.DataFrame(),
    )

    assert direct.to_function_template() == reference.to_function_template()
    assert direct.to_function_template().returns == "dataframe"


def test_bound_argument_types_are_inferred_and_nullable_dataframe_is_preserved() -> None:
    template = authoring.Bind(
        maybe_dataframe,
        value=authoring.ref.dataset(),
    ).to_function_template()

    assert template.args["value"].type == "dataframe | null"


@pytest.mark.parametrize(
    ("dataframe_inputs", "returns", "expected_signature", "expected_operation"),
    [
        (0, "dataframe", (0, 1), "read"),
        (1, "none", (1, 0), "write"),
        (1, "dataframe", (1, 1), "transform"),
        (2, "dataframe", (2, 1), "combine"),
        (0, "any", (None, None), "workflow"),
        (0, "none", (0, 0), "unknown"),
        (2, "none", (2, 0), "unknown"),
    ],
)
def test_frame_operation_is_inferred_from_dataframe_signature(
    dataframe_inputs: int,
    returns: str,
    expected_signature: tuple[int | None, int | None],
    expected_operation: str,
) -> None:
    function = spec_model.FunctionTemplate(
        id="operation",
        returns=returns,
        entrypoint="operations:operation",
        args={
            f"frame_{index}": spec_model.Argument(id=f"frame_{index}", type="dataframe")
            for index in range(dataframe_inputs)
        },
    )

    assert function.frame_signature == expected_signature
    assert function.frame_operation == expected_operation
    assert "frame_operation" not in function.model_dump()


def test_explicit_argument_contract_overrides_bound_value_inference() -> None:
    callable_with_explicit_args = functions.function(
        returns="dataframe",
        args={"value": "string"},
    )(dataframe)
    template = authoring.Bind(
        callable_with_explicit_args,
        value=authoring.ref.dataset(),
    ).to_function_template()

    assert template.args["value"].type == "string"


def test_disabled_signature_inspection_requires_explicit_contract() -> None:
    with pytest.raises(ValueError, match="requires explicit args and returns"):
        ref.function(scalar_result, validate_signature=False)
    with pytest.raises(ValueError, match="requires explicit args and returns"):
        functions.function(validate_signature=False)


def test_disabled_signature_inspection_still_checks_exact_names_and_dataframe_arity() -> None:
    function = ref.function(
        scalar_result,
        returns="dataframe",
        args={"value": "dataframe"},
        validate_signature=False,
    )
    operator = authoring.Operator(
        id="calculate",
        outputs=[],
        compute=authoring.Bind(
            function,
            other=authoring.ref.dataset(),
        ),
    )
    with pytest.raises(ValueError, match="match the explicit function args contract"):
        operator.function_catalog()

    over_arity = ref.function(
        scalar_result,
        returns="dataframe",
        args={"first": "dataframe", "second": "dataframe"},
        validate_signature=False,
    )
    operator = authoring.Operator(
        id="calculate",
        outputs=[],
        compute=authoring.Bind(
            over_arity,
            first=authoring.ref.dataset(),
            second=authoring.ref.dataset(),
        ),
    )
    with pytest.raises(ValueError, match="invalid dataframe arity"):
        operator.function_catalog()


def test_decorator_metadata_conflicts_are_rejected() -> None:
    with pytest.raises(ValueError, match="Return contract conflicts"):
        ref.function(explicit_result, returns="none")

    with pytest.raises(ValueError, match="Argument contract conflicts"):
        ref.function(
            functions.function(returns="dataframe", args={"value": "string"})(args_callable),
            args={"value": "integer"},
        )


def test_reference_metadata_only_contract_is_deferred_until_catalog_binding() -> None:
    reference = ref.function("missing_optional_reference:calculate")
    assert reference.returns is None
    assert reference.args is None

    operator = authoring.Operator(
        id="calculate",
        outputs=[],
        compute=authoring.Bind(
            reference,
        ),
    )
    with pytest.raises(ValueError, match="Explicit returns metadata is required"):
        operator.function_catalog()
