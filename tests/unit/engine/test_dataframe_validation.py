"""Dataframe validation contracts and fail-fast ordering."""

import dataclasses
import logging
import types

import polars as pl
import pytest

from uptimely import execution_plan
from uptimely.engine.dataframe import backend
from uptimely.engine.dataframe import validation as dataframe_validation
from uptimely.spec import functions


def _invocation(kind: functions.FunctionKindId = "read") -> execution_plan.Invocation:
    return execution_plan.Invocation(
        id="invocation",
        function_kind=kind,
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="dataset",
    )


def _validator(
    adapter: backend.PolarsBackend,
    frame: object,
    dimensions: list[str],
    *,
    fragment: bool,
    invalid_frame_message: str | None = None,
    column_types: dict[str, str] | None = None,
) -> dataframe_validation.FragmentValidator | dataframe_validation.MainFrameValidator:
    types = column_types if column_types is not None else {}
    if fragment:
        return dataframe_validation.FragmentValidator(
            adapter,
            frame,
            dimensions,
            "Frame",
            invalid_frame_message=invalid_frame_message,
            column_types=types,
            invocation=_invocation(),
        )
    return dataframe_validation.MainFrameValidator(
        adapter,
        frame,
        dimensions,
        "Frame",
        invalid_frame_message=invalid_frame_message,
        column_types=types,
    )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("fragment", [False, True])
@pytest.mark.parametrize(
    ("data", "dimensions", "message"),
    [
        ({"value": [1]}, ["key"], "missing dimension columns: key"),
        ({"key": ["A", "A"]}, ["key"], "duplicate dimension keys"),
        ({"value": [1, 2]}, [], "dimensionless profile frames allow at most one row"),
    ],
)
def test_shared_structural_contracts(
    lazy: bool,
    fragment: bool,
    data: dict[str, list[str] | list[int]],
    dimensions: list[str],
    message: str,
) -> None:
    frame = pl.DataFrame(data)
    validator = _validator(
        backend.PolarsBackend(),
        frame.lazy() if lazy else frame,
        dimensions,
        fragment=fragment,
    )
    with pytest.raises(ValueError, match=message):
        validator.validate()


@pytest.mark.parametrize("fragment", [False, True])
def test_invalid_frame_fails_before_schema_access(
    monkeypatch: pytest.MonkeyPatch, fragment: bool
) -> None:
    adapter = backend.PolarsBackend()

    def unexpected_schema(frame: object) -> list[str]:
        pytest.fail("Schema access must not follow failed frame validation")

    monkeypatch.setattr(adapter, "column_names", unexpected_schema)
    validator = _validator(
        adapter, object(), ["key"], fragment=fragment, invalid_frame_message="invalid raw frame"
    )
    with pytest.raises(ValueError, match="invalid raw frame"):
        validator.validate()


@pytest.mark.parametrize("fragment", [False, True])
def test_missing_dimensions_fail_before_key_checks(
    monkeypatch: pytest.MonkeyPatch, fragment: bool
) -> None:
    adapter = backend.PolarsBackend()

    def unexpected_select(frame: object, columns: object) -> object:
        pytest.fail("Key checks must not follow missing dimensions")

    monkeypatch.setattr(adapter, "select", unexpected_select)
    validator = _validator(adapter, pl.DataFrame({"value": [1]}), ["key"], fragment=fragment)
    with pytest.raises(ValueError, match="missing dimension columns: key"):
        validator.validate()


def _vectorize_validator(
    frame: pl.DataFrame, comparison_frame: pl.DataFrame | None
) -> dataframe_validation.FragmentValidator:
    return dataframe_validation.FragmentValidator(
        backend.PolarsBackend(),
        frame,
        ["key"],
        "Fragment",
        invocation=_invocation("vectorize"),
        comparison_frame=comparison_frame,
    )


def test_equal_row_count_does_not_prove_identical_keys() -> None:
    validator = _vectorize_validator(
        pl.DataFrame({"key": ["new"]}), pl.DataFrame({"key": ["existing"]})
    )
    with pytest.raises(ValueError, match="preserve the profile grain keys"):
        validator.validate()


def test_row_count_failure_precedes_key_identity_failure() -> None:
    validator = _vectorize_validator(
        pl.DataFrame({"key": ["existing", "new"]}), pl.DataFrame({"key": ["existing"]})
    )
    with pytest.raises(ValueError, match="preserve the accumulated profile row count"):
        validator.validate()


@pytest.mark.parametrize(
    ("row_count_relation", "key_relation", "message"),
    [
        ("same", "unrestricted", "preserve the accumulated profile row count"),
        ("unrestricted", "identical", "preserve the profile grain keys"),
        ("unrestricted", "unrestricted", None),
    ],
)
def test_kind_contracts_are_independent_and_not_hard_coded(
    monkeypatch: pytest.MonkeyPatch,
    row_count_relation: functions.RowCountRelation,
    key_relation: functions.KeyRelation,
    message: str | None,
) -> None:
    validator = _vectorize_validator(
        pl.DataFrame({"key": ["new", "another"]}), pl.DataFrame({"key": ["existing"]})
    )
    definitions = dict(functions.FUNCTION_KINDS)
    definitions[functions.VECTORIZE] = dataclasses.replace(
        definitions[functions.VECTORIZE],
        row_count_relation=row_count_relation,
        key_relation=key_relation,
    )
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))
    if message is None:
        validator.validate()
    else:
        with pytest.raises(ValueError, match=message):
            validator.validate()


def test_preservation_requires_the_accumulated_target() -> None:
    validator = _vectorize_validator(pl.DataFrame({"key": ["new"]}), None)
    with pytest.raises(ValueError, match="preserve the accumulated profile row count"):
        validator.validate()


def test_fragment_output_override_preserves_empty_outputs() -> None:
    validator = dataframe_validation.FragmentValidator(
        backend.PolarsBackend(),
        pl.DataFrame({"key": ["existing"]}),
        ["key"],
        "Fragment",
        invocation=_invocation(),
    )
    validator.invocation.output_features.append("result")
    assert validator.effective_output_features == ["result"]
    with pytest.raises(ValueError, match="missing output columns: result"):
        validator.validate()
    overridden = dataclasses.replace(validator, output_features=[])
    assert overridden.effective_output_features == []
    overridden.validate()


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("fragment", [False, True])
@pytest.mark.parametrize("value", [2, "wrong"])
def test_declared_types_without_spec(lazy: bool, fragment: bool, value: int | str) -> None:
    frame = pl.DataFrame({"key": ["A"], "value": [value]})
    validator = _validator(
        backend.PolarsBackend(),
        frame.lazy() if lazy else frame,
        ["key"],
        fragment=fragment,
        column_types={"key": "string", "value": "integer", "future_output": "float"},
    )
    assert not hasattr(validator, "dataset")
    if isinstance(validator, dataframe_validation.FragmentValidator):
        validator = dataclasses.replace(validator, output_features=["value"])
    if isinstance(value, str):
        with pytest.raises(ValueError, match="Output column value.*expected integer"):
            validator.validate()
    else:
        validator.validate()


def test_fragment_ignores_types_of_undeclared_extra_columns() -> None:
    validator = dataframe_validation.FragmentValidator(
        backend.PolarsBackend(),
        pl.DataFrame({"key": ["A"], "extra": ["not an integer"]}),
        ["key"],
        "Fragment",
        column_types={"key": "string", "extra": "integer"},
        invocation=_invocation(),
    )
    validator.validate()


def test_main_frame_checks_structure_once(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = backend.PolarsBackend()
    calls: list[object] = []
    is_frame = adapter.is_frame

    def count_frame_checks(frame: object) -> bool:
        calls.append(frame)
        return is_frame(frame)

    monkeypatch.setattr(adapter, "is_frame", count_frame_checks)
    frame = pl.DataFrame({"key": ["A"]})
    dataframe_validation.MainFrameValidator(adapter, frame, ["key"], "Main frame").validate()
    assert len(calls) == 1
    assert calls[0] is frame


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("collision", [False, True])
def test_main_frame_merge_validation(lazy: bool, collision: bool) -> None:
    frame = pl.DataFrame({"key": ["A"], "value": [1]})
    fragment = pl.DataFrame({"key": ["A"], "value" if collision else "new": [2]})
    validator = dataframe_validation.MainFrameValidator(
        backend.PolarsBackend(), frame.lazy() if lazy else frame, ["key"], "Main frame"
    )
    contribution = fragment.lazy() if lazy else fragment
    if collision:
        with pytest.raises(ValueError, match="overlap the accumulated profile frame: value"):
            validator.validate_merge(contribution)
    else:
        validator.validate_merge(contribution)


@pytest.mark.parametrize("fragment", [False, True])
def test_validation_debug_logs_identify_checks_and_inapplicable_contracts(
    caplog: pytest.LogCaptureFixture, fragment: bool
) -> None:
    caplog.set_level(logging.DEBUG, logger=dataframe_validation.__name__)
    validator = _validator(
        backend.PolarsBackend(),
        pl.DataFrame({"key": ["A"]}),
        ["key"],
        fragment=fragment,
        column_types={"key": "string"},
    )
    validator.validate()

    messages = [record.getMessage() for record in caplog.records]
    assert messages[:4] == [
        "  Fragment:" if fragment else "  Main frame:",
        "    - checking dataframe type",
        "    - checking required dimension columns",
        "    - skipping dimensionless row count (data has dimensions)",
    ]
    assert messages.count("  Fragment:" if fragment else "  Main frame:") == 1
    assert "    - checking dimension-key uniqueness" in messages
    assert "      Declared types: {'key': 'string'}" in messages
    if fragment:
        assert "    - checking declared output columns" in messages
        assert "    - checking dimension and output types" in messages
        assert "    - skipping row-count preservation (not required)" in messages
        assert "    - skipping dimension-key preservation (not required)" in messages
    else:
        assert "    - checking types of present columns" in messages
    assert all(record.levelno == logging.DEBUG for record in caplog.records)


def test_validation_failure_logs_only_attempted_checks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=dataframe_validation.__name__)
    validator = _validator(backend.PolarsBackend(), object(), ["key"], fragment=True)
    with pytest.raises(ValueError, match="must be a Polars"):
        validator.validate()
    assert caplog.messages == ["  Fragment:", "    - checking dataframe type"]


def test_dimensionless_and_merge_validation_debug_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=dataframe_validation.__name__)
    validator = dataframe_validation.MainFrameValidator(
        backend.PolarsBackend(), pl.DataFrame({"value": [1]}), [], "Global data"
    )
    validator.validate()
    validator.validate_merge(pl.DataFrame({"other": [2]}))
    assert caplog.messages[0] == "  Main frame:"
    assert "    - checking dimensionless row count" in caplog.messages
    assert "    - skipping dimension-key uniqueness (no dimensions)" in caplog.messages
    assert caplog.messages[-1] == "    - checking fragment feature collisions"


def test_preservation_validation_debug_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=dataframe_validation.__name__)
    _vectorize_validator(pl.DataFrame({"key": ["A"]}), pl.DataFrame({"key": ["A"]})).validate()
    assert "    - checking row-count preservation" in caplog.messages
    assert "    - checking dimension-key preservation" in caplog.messages
