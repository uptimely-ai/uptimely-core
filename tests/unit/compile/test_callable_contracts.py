"""Compiler checks for callable compatibility with declared function contracts."""

import functools
import graphlib
import inspect
import logging

import pytest

from uptimely import entrypoint
from uptimely.compiler import validation
from uptimely.spec import model as spec_model
from uptimely.spec import operator_kinds
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


def variadic_positional_dataframe(*frame: DataFrame) -> DataFrame:
    return frame[0]


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
    returns: operator_kinds.ReturnKind = "dataframe",
) -> spec_model.FunctionTemplate:
    return spec_model.FunctionTemplate(
        id="calculate",
        returns=returns,
        entrypoint=f"{__name__}:typed_dataframe",
        args={
            name: spec_model.Argument(id=name, type=argument_type)
            for name, argument_type in (arguments or {"frame": "dataframe"}).items()
        },
    )


def _signature(name: str) -> entrypoint.Signature:
    function = entrypoint.Function(entrypoint.Module(__name__), name)
    return function.read_signature()


@pytest.mark.parametrize("validate", validation.VALIDATION_DEPENDENCIES, ids=lambda f: f.__name__)
def test_callable_rules_do_not_repeat_per_function_logs(
    caplog: pytest.LogCaptureFixture, validate: validation.Validator
) -> None:
    caplog.set_level(logging.DEBUG, logger=validation.__name__)
    context = validation.CallableValidationContext(
        _function_template(), _signature("typed_dataframe")
    )

    validate(context)

    assert not caplog.records


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_callable_validation_does_not_repeat_summary(
    caplog: pytest.LogCaptureFixture, level: int
) -> None:
    caplog.set_level(level, logger=validation.__name__)

    validation.validation_callable_signature(
        validation.CallableValidationContext(_function_template(), _signature("typed_dataframe"))
    )

    assert not caplog.messages


def test_failed_signature_validation_preserves_function_diagnostic(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=validation.__name__)

    with pytest.raises(errors.SpecError, match="positional-only") as error:
        validation.validation_callable_signature(
            validation.CallableValidationContext(
                _function_template(), _signature("positional_only_dataframe")
            )
        )

    assert error.value.path == ("functions", "calculate", "args", "frame")
    assert not caplog.messages


@pytest.mark.parametrize("implementation", ["untyped_dataframe", "accepts_kwargs"])
def test_signature_validation_does_not_log_individual_annotation_skips(
    caplog: pytest.LogCaptureFixture, implementation: str
) -> None:
    caplog.set_level(logging.DEBUG, logger=validation.__name__)

    validation.validation_callable_signature(
        validation.CallableValidationContext(_function_template(), _signature(implementation))
    )

    assert not caplog.messages


def test_unrestricted_return_annotation_skip_is_quiet(caplog: pytest.LogCaptureFixture) -> None:
    function = _function_template(returns="any")
    caplog.set_level(logging.DEBUG, logger=validation.__name__)

    validation.validation_return_annotation(
        validation.CallableValidationContext(function, _signature("typed_dataframe"))
    )

    assert not caplog.messages


def test_callable_validation_dependencies_are_acyclic() -> None:
    dependencies = validation.VALIDATION_DEPENDENCIES
    ordered = tuple(graphlib.TopologicalSorter(dependencies).static_order())

    assert ordered == tuple(dependencies)
    assert all(
        prerequisite in dependencies
        for prerequisites in dependencies.values()
        for prerequisite in prerequisites
    )


def test_callable_validation_stops_after_a_failed_prerequisite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    context = validation.CallableValidationContext(
        _function_template(), _signature("typed_dataframe")
    )

    def failing_validator(context: validation.CallableValidationContext) -> None:
        calls.append("failing")
        raise ValueError("invalid callable signature")

    def dependent_validator(context: validation.CallableValidationContext) -> None:
        calls.append("dependent")

    monkeypatch.setattr(
        validation,
        "VALIDATION_DEPENDENCIES",
        {failing_validator: (), dependent_validator: (failing_validator,)},
    )

    with pytest.raises(ValueError, match="invalid callable signature"):
        validation.validation_callable_signature(context)

    assert calls == ["failing"]


def test_signature_inspection_follows_wrapped_callable() -> None:
    signature = _signature("wrapped_dataframe")

    assert signature.parameters["frame"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.args["frame"] == "DataFrame | LazyFrame"


def test_signature_properties_follow_current_parameters() -> None:
    signature = _signature("requires_extra_parameter")
    assert list(signature.required_parameters) == ["frame", "required"]
    assert not signature.accepts_kwargs
    signature.parameters = _signature("accepts_kwargs").parameters
    assert signature.accepts_kwargs
    assert signature.required_parameters == {}
    signature.parameters = _signature("defaulted_extra_parameter").parameters
    assert list(signature.required_parameters) == ["frame"]


def test_typed_and_untyped_callables_satisfy_supported_contracts() -> None:
    function = _function_template()

    validation.validation_callable_signature(
        validation.CallableValidationContext(function, _signature("typed_dataframe"))
    )
    validation.validation_callable_signature(
        validation.CallableValidationContext(function, _signature("untyped_dataframe"))
    )


def test_callable_must_accept_declared_arguments_as_keywords() -> None:
    function = _function_template()

    with pytest.raises(errors.SpecError, match="positional-only") as error:
        validation.validation_callable_signature(
            validation.CallableValidationContext(function, _signature("positional_only_dataframe"))
        )

    assert error.value.code == "invalid_implementation_signature"
    assert error.value.path == ("functions", "calculate", "args", "frame")


def test_var_positional_parameter_does_not_accept_a_declared_keyword() -> None:
    with pytest.raises(errors.SpecError, match="cannot be passed as a keyword"):
        validation.validation_callable_signature(
            validation.CallableValidationContext(
                _function_template(), _signature("variadic_positional_dataframe")
            )
        )


def test_callable_cannot_require_undeclared_parameters() -> None:
    with pytest.raises(errors.SpecError, match="requires undeclared parameter 'required'"):
        validation.validation_callable_signature(
            validation.CallableValidationContext(
                _function_template(), _signature("requires_extra_parameter")
            )
        )


def test_declared_arguments_are_forwarded_to_kwargs_and_defaults_are_allowed() -> None:
    validation.validation_callable_signature(
        validation.CallableValidationContext(_function_template(), _signature("accepts_kwargs"))
    )
    validation.validation_callable_signature(
        validation.CallableValidationContext(
            _function_template(), _signature("defaulted_extra_parameter")
        )
    )


def test_nested_declared_argument_types_are_compared_recursively() -> None:
    function = _function_template(
        arguments={
            "values": "array[integer]",
            "options": "object{str: array[integer]}",
        }
    )
    signature = _signature("nested_arguments")

    validation.validation_callable_signature(
        validation.CallableValidationContext(function, signature)
    )


def test_supported_argument_annotation_must_match_declared_type() -> None:
    with pytest.raises(errors.SpecError, match="declares argument type dataframe"):
        validation.validation_callable_signature(
            validation.CallableValidationContext(
                _function_template(), _signature("wrong_argument_annotation")
            )
        )


def test_missing_return_annotation_is_permitted_but_none_contradicts_dataframe() -> None:
    validation.validation_callable_signature(
        validation.CallableValidationContext(_function_template(), _signature("untyped_dataframe"))
    )
    with pytest.raises(errors.SpecError, match="expected DataFrame or LazyFrame") as error:
        validation.validation_callable_signature(
            validation.CallableValidationContext(
                _function_template(), _signature("wrong_return_annotation")
            )
        )

    assert error.value.path == ("functions", "calculate", "returns")
