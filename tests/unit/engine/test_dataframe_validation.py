"""Dataframe validation contracts owned by fragments and datasets."""

import logging

import polars as pl
import pytest

from uptimely import plan as plan_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import function_kinds as function_kinds_module


def _invocation(
    kind: function_kinds_module.FunctionKindId = "read",
    *,
    output_features: list[str] | None = None,
    column_types: dict[str, str] | None = None,
) -> plan_module.Invocation:
    return plan_module.Invocation(
        id="invocation",
        function_kind=kind,
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        dataset_id="dataset",
        id_columns=["key"],
        output_features=output_features or [],
        column_types=column_types or {},
    )


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("data", "dimensions", "message"),
    [
        ({"value": [1]}, ("key",), "missing dimension columns: key"),
        ({"key": ["A", "A"]}, ("key",), "duplicate dimension keys"),
        ({"value": [1, 2]}, (), "dimensionless profile frames allow at most one row"),
    ],
)
def test_fragment_checks_structure_and_keys(
    lazy: bool,
    data: dict[str, list[str] | list[int]],
    dimensions: tuple[str, ...],
    message: str,
) -> None:
    invocation = _invocation()
    fragment = fragment_module.Fragment(pl.DataFrame(data), dimensions, invocation)
    if lazy:
        fragment = fragment_module.Fragment(fragment.dataframe.lazy(), dimensions, invocation)

    with pytest.raises(ValueError, match=message):
        fragment.validate_invocation_result(backend_module.PolarsBackend(), invocation)


def test_fragment_checks_required_outputs_even_without_content_validation() -> None:
    invocation = _invocation(output_features=["result"])
    fragment = fragment_module.Fragment(pl.DataFrame({"key": ["A"]}), ("key",), invocation)

    with pytest.raises(ValueError, match="missing output columns: result"):
        fragment.validate_invocation_result(
            backend_module.PolarsBackend(), invocation, validate_content=False
        )


def test_fragment_checks_only_declared_column_types() -> None:
    invocation = _invocation(
        output_features=["value"],
        column_types={"key": "string", "value": "integer", "future": "float"},
    )
    fragment = fragment_module.Fragment(
        pl.DataFrame({"key": ["A"], "value": [2], "extra": ["ignored"]}),
        ("key",),
        invocation,
    )

    fragment.validate_invocation_result(backend_module.PolarsBackend(), invocation)

    invalid = fragment_module.Fragment(
        pl.DataFrame({"key": ["A"], "value": ["wrong"]}),
        ("key",),
        invocation,
    )
    with pytest.raises(ValueError, match="Output column value.*expected integer"):
        invalid.validate_invocation_result(backend_module.PolarsBackend(), invocation)


@pytest.mark.parametrize("lazy", [False, True])
def test_dataset_validates_structure_keys_and_types(lazy: bool) -> None:
    frame = pl.DataFrame({"key": ["A", "A"], "value": [1, 2]})
    dataset = dataset_module.Dataset(
        backend_module.PolarsBackend(),
        ["key"],
        frame.lazy() if lazy else frame,
    )
    with pytest.raises(ValueError, match="duplicate dimension keys"):
        dataset.validate_accumulated_frame()

    valid = dataset_module.Dataset(
        backend_module.PolarsBackend(),
        ["key"],
        pl.DataFrame({"key": ["A"], "value": ["wrong"]}),
    )
    with pytest.raises(ValueError, match="Output column value.*expected integer"):
        valid.validate_accumulated_frame(column_types={"key": "string", "value": "integer"})


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("collision", [False, True])
def test_dataset_rejects_merge_feature_collisions(lazy: bool, collision: bool) -> None:
    backend = backend_module.PolarsBackend()
    dataset = dataset_module.Dataset(
        backend,
        ["key"],
        pl.DataFrame({"key": ["A"], "value": [1]}),
    )
    frame = pl.DataFrame({"key": ["A"], "value" if collision else "new": [2]})
    fragment = fragment_module.Fragment(
        frame.lazy() if lazy else frame,
        ("key",),
    )

    if collision:
        with pytest.raises(ValueError, match="overlap the accumulated profile frame: value"):
            dataset.validate_fragment_merge(fragment)
    else:
        dataset.validate_fragment_merge(fragment)


@pytest.mark.parametrize(
    ("result", "target", "fragment_frame", "message"),
    [
        (
            pl.DataFrame({"key": ["A"]}),
            pl.DataFrame({"key": ["A"]}),
            pl.DataFrame({"key": ["A"], "value": [1]}),
            "missing required columns: value",
        ),
        (
            pl.DataFrame({"key": ["A"], "value": [1], "extra": [2]}),
            None,
            pl.DataFrame({"key": ["A"], "value": [1]}),
            "contains undeclared columns: extra",
        ),
    ],
)
def test_candidate_dataset_checks_complete_merge_schema(
    result: pl.DataFrame,
    target: pl.DataFrame | None,
    fragment_frame: pl.DataFrame,
    message: str,
) -> None:
    backend = backend_module.PolarsBackend()
    candidate = dataset_module.Dataset(backend, ["key"], result)
    fragment = fragment_module.Fragment(fragment_frame, ("key",))

    with pytest.raises(ValueError, match=message):
        candidate.validate_merge_candidate(
            target,
            fragment,
            description="Merge result",
        )


def test_candidate_dataset_skips_optional_checks_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = backend_module.PolarsBackend()
    candidate = dataset_module.Dataset(
        backend,
        ["key"],
        pl.DataFrame({"key": ["A", "A"], "value": ["wrong", "wrong"]}),
    )
    fragment = fragment_module.Fragment(
        pl.DataFrame({"key": ["A"], "value": ["wrong"]}),
        ("key",),
    )

    def unexpected_check(*args: object, **kwargs: object) -> object:
        pytest.fail("Optional candidate checks must be skipped when validation is disabled")

    monkeypatch.setattr(backend, "row_count", unexpected_check)
    monkeypatch.setattr(backend, "is_duplicated", unexpected_check)
    monkeypatch.setattr(backend, "validate_types", unexpected_check)
    candidate.validate_merge_candidate(None, fragment, description="Merge result")


def test_executor_checks_vectorized_contract_and_preservation() -> None:
    invocation = _invocation("vectorize", output_features=["new"])
    backend = backend_module.PolarsBackend()
    executor = execution_module.InvocationExecutor(
        backend,
        {},
        {},
        state_module.RuntimeState(),
    )
    dataset = dataset_module.Dataset(
        backend,
        ["key"],
        pl.DataFrame({"key": ["A"], "value": [1]}),
    )
    comparison = dataset.dataframe

    with pytest.raises(ValueError, match="must preserve existing column values and row order"):
        executor._validate_vectorized_result(
            pl.DataFrame({"key": ["A"], "value": [9], "new": [2]}),
            invocation,
            comparison,
            preserve_data=True,
        )
    assert executor._validate_vectorized_result(
        pl.DataFrame({"key": ["A"], "value": [1], "new": [2]}),
        invocation,
        comparison,
        preserve_data=True,
    ) == ["new"]


def test_vectorized_validation_skips_content_comparison_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocation = _invocation("vectorize", output_features=["new"])
    backend = backend_module.PolarsBackend()
    dataset = dataset_module.Dataset(
        backend,
        ["key"],
        pl.DataFrame({"key": ["A"]}),
    )
    executor = execution_module.InvocationExecutor(
        backend,
        {},
        {},
        state_module.RuntimeState(),
    )
    monkeypatch.setattr(
        backend,
        "same_data",
        lambda *_args, **_kwargs: pytest.fail("Content comparison should be skipped"),
    )

    assert executor._validate_vectorized_result(
        pl.DataFrame({"key": ["A"], "new": [2]}),
        invocation,
        dataset.dataframe,
        preserve_data=False,
    ) == ["new"]


@pytest.mark.parametrize(
    ("frame", "outputs", "comparison", "message"),
    [
        (
            pl.DataFrame({"value": [1]}),
            ["new"],
            pl.DataFrame({"key": ["A"]}),
            "missing dimension columns: key",
        ),
        (
            pl.DataFrame({"key": ["A"]}),
            ["new"],
            pl.DataFrame({"key": ["A"]}),
            "missing output columns: new",
        ),
        (
            pl.DataFrame({"key": ["A"], "new": [1]}),
            ["new"],
            pl.DataFrame({"key": ["A"], "new": [2]}),
            "cannot replace existing columns: new",
        ),
        (
            pl.DataFrame({"key": ["A"], "new": [1]}),
            ["new"],
            pl.DataFrame({"key": ["A"], "value": [2]}),
            "must preserve existing columns: value",
        ),
        (
            pl.DataFrame({"key": ["A"], "new": [1], "extra": [2]}),
            ["new"],
            pl.DataFrame({"key": ["A"]}),
            "returned undeclared columns: extra",
        ),
    ],
)
def test_executor_rejects_invalid_vectorized_schema(
    frame: pl.DataFrame,
    outputs: list[str],
    comparison: pl.DataFrame,
    message: str,
) -> None:
    invocation = _invocation("vectorize", output_features=outputs)
    executor = execution_module.InvocationExecutor(
        backend_module.PolarsBackend(),
        {},
        {},
        state_module.RuntimeState(),
    )

    with pytest.raises(ValueError, match=message):
        executor._validate_vectorized_result(frame, invocation, comparison, preserve_data=False)


def test_owner_validation_logs_checks(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=fragment_module.__name__)
    invocation = _invocation()
    fragment_module.Fragment(
        pl.DataFrame({"key": ["A"]}),
        ("key",),
        invocation,
    ).validate_invocation_result(backend_module.PolarsBackend(), invocation)
    assert "  Fragment:" in caplog.messages
    assert "    - checking dataframe type" in caplog.messages
    assert "    - checking declared output columns" in caplog.messages

    caplog.clear()
    caplog.set_level(logging.DEBUG, logger=dataset_module.__name__)
    dataset_module.Dataset(
        backend_module.PolarsBackend(),
        [],
        pl.DataFrame({"value": [1]}),
    ).validate_accumulated_frame()
    assert "  Dataset:" in caplog.messages
    assert "    - checking dimensionless row count" in caplog.messages
