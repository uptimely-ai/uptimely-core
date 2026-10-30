"""Compiler checks for callable compatibility with declared function contracts."""

import functools
import inspect

import pytest

from uptimely import entrypoint
from uptimely.compiler import inspection
from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors


class DataFrame:
    """Test stand-in for a supported dataframe annotation."""


class LazyFrame:
    """Test stand-in for a supported lazy dataframe annotation."""


def typed_dataframe(frame: DataFrame | LazyFrame) -> DataFrame | LazyFrame:
    return frame


def untyped_dataframe(frame):
    return frame


def positional_only_dataframe(frame: DataFrame, /) -> DataFrame:
    return frame


def requires_extra_parameter(frame: DataFrame, required: str) -> DataFrame:
    assert required
    return frame


def wrong_argument_annotation(frame: str) -> DataFrame:
    assert isinstance(frame, str)
    return DataFrame()


def wrong_return_annotation(frame: DataFrame) -> None:
    assert isinstance(frame, DataFrame)
    return


def accepts_kwargs(**arguments: object) -> object:
    return arguments


def defaulted_extra_parameter(frame: DataFrame, optional: str = "") -> DataFrame:
    assert isinstance(optional, str)
    return frame


def nested_arguments(values: list[int], options: dict[str, list[int]]) -> DataFrame:
    assert isinstance(values, list)
    assert isinstance(options, dict)
    return DataFrame()


@functools.wraps(typed_dataframe)
def wrapped_dataframe(*args: object, **kwargs: object) -> object:
    assert args or kwargs
    return DataFrame()


def _function_template(
    *,
    arguments: dict[str, str] | None = None,
    returns: functions.ReturnKind = "dataframe",
) -> spec_model.FunctionTemplate:
    return spec_model.FunctionTemplate(
        id="calculate",
        kind="vectorize",
        returns=returns,
        entrypoint=f"{__name__}:typed_dataframe",
        args={
            name: spec_model.Argument(id=name, type=argument_type)
            for name, argument_type in (arguments or {"frame": "dataframe"}).items()
        },
    )


def _signature(name: str) -> entrypoint.Signature:
    function = entrypoint.Function(entrypoint.Module(__name__), name)
    return function.signature


def test_signature_inspection_follows_wrapped_callable() -> None:
    signature = _signature("wrapped_dataframe")

    assert signature.parameters["frame"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.args["frame"] == "DataFrame | LazyFrame"


def test_typed_and_untyped_callables_satisfy_supported_contracts() -> None:
    function = _function_template()

    inspection.validate_callable_signature(function, _signature("typed_dataframe"))
    inspection.validate_callable_signature(function, _signature("untyped_dataframe"))


def test_callable_must_accept_declared_arguments_as_keywords() -> None:
    function = _function_template()

    with pytest.raises(errors.SpecError, match="positional-only") as error:
        inspection.validate_callable_signature(function, _signature("positional_only_dataframe"))

    assert error.value.code == "invalid_implementation_signature"
    assert error.value.path == ("functions", "calculate", "args", "frame")


def test_callable_cannot_require_undeclared_parameters() -> None:
    with pytest.raises(errors.SpecError, match="requires undeclared parameter 'required'"):
        inspection.validate_callable_signature(
            _function_template(), _signature("requires_extra_parameter")
        )


def test_declared_arguments_are_forwarded_to_kwargs_and_defaults_are_allowed() -> None:
    inspection.validate_callable_signature(_function_template(), _signature("accepts_kwargs"))
    inspection.validate_callable_signature(
        _function_template(), _signature("defaulted_extra_parameter")
    )


def test_nested_declared_argument_types_are_compared_recursively() -> None:
    function = _function_template(
        arguments={
            "values": "array[integer]",
            "options": "object{str: array[integer]}",
        }
    )
    signature = _signature("nested_arguments")

    inspection.validate_callable_signature(function, signature)


def test_supported_argument_annotation_must_match_declared_type() -> None:
    with pytest.raises(errors.SpecError, match="declares argument type dataframe"):
        inspection.validate_callable_signature(
            _function_template(), _signature("wrong_argument_annotation")
        )


def test_missing_return_annotation_is_permitted_but_none_contradicts_dataframe() -> None:
    inspection.validate_callable_signature(_function_template(), _signature("untyped_dataframe"))
    with pytest.raises(errors.SpecError, match="expected DataFrame or LazyFrame") as error:
        inspection.validate_callable_signature(
            _function_template(), _signature("wrong_return_annotation")
        )

    assert error.value.path == ("functions", "calculate", "returns")
