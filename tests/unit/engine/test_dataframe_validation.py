"""Dataframe validation contracts owned by fragments and datasets."""

import logging

import polars as pl
import pytest

from uptimely import plan as plan_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.dataframe import merge as merge_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import operator_kinds as operator_kinds_module


def _invocation(
    kind: operator_kinds_module.OperatorKindId = "read",
    *,
    output_features: list[str] | None = None,
    column_types: dict[str, str] | None = None,
) -> plan_module.Invocation:
    return plan_module.Invocation(
        id="invocation",
        role="compute",
        result="target" if kind == "vectorize" else "fragment",
        operator_kind=kind,
        dataframe_input_scope=operator_kinds_module.OPERATOR_KINDS[kind].dataframe_input_scope,
        fragment_dimensions=operator_kinds_module.OPERATOR_KINDS[kind].fragment_dimensions,
        row_count_relation=operator_kinds_module.OPERATOR_KINDS[kind].row_count_relation,
        key_relation=operator_kinds_module.OPERATOR_KINDS[kind].key_relation,
        row_order_relation=operator_kinds_module.OPERATOR_KINDS[kind].row_order_relation,
        existing_data_relation=operator_kinds_module.OPERATOR_KINDS[kind].existing_data_relation,
        entrypoint="test:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="dataset",
        target_grain_keys=["key"],
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


@pytest.mark.parametrize("validate", [False, True])
def test_read_retains_dimension_identifiers_without_feature_outputs(validate: bool) -> None:
    invocation = _invocation(
        output_features=["value"],
        column_types={"key": "string", "series": "string", "category": "string", "value": "float"},
    ).__replace__(fragment_identifiers=["series", "category"])
    frame = pl.LazyFrame(
        {"key": ["p1", "p2"], "series": ["s1", "s1"], "value": [90.0, 80.0], "extra": [1, 2]}
    )

    fragment = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(), invocation, lambda: frame, validate=validate
    )

    assert fragment.dimensions == ("key",)
    assert fragment.dataframe.collect().columns == ["key", "value", "series"]
    assert invocation.output_features == ["value"]
    assert fragment.dataframe.collect()["series"].to_list() == ["s1", "s1"]


def test_read_validates_carried_identifier_types() -> None:
    invocation = _invocation(
        output_features=["value"], column_types={"series": "string"}
    ).__replace__(fragment_identifiers=["series"])

    with pytest.raises(ValueError, match="Output column series.*expected string"):
        fragment_module.Fragment.stage(
            backend_module.PolarsBackend(),
            invocation,
            lambda: pl.LazyFrame({"key": ["p1"], "series": [1], "value": [90.0]}),
            validate=True,
        )


@pytest.mark.parametrize("validate", [False, True])
def test_expand_fragment_retains_parent_identifiers(validate: bool) -> None:
    invocation = _invocation("expand", output_features=["value"]).__replace__(
        fragment_identifiers=["series"],
        column_types={"series": "string", "value": "float"},
    )
    frame = pl.LazyFrame({"series": ["s1", "s2"], "value": [90.0, 80.0], "extra": [1, 2]})

    fragment = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(), invocation, lambda: frame, validate=validate
    )

    assert fragment.dimensions == ("series",)
    assert fragment.dataframe.collect().columns == ["series", "value"]


def test_expand_fragment_retains_only_present_resolution_identifiers() -> None:
    invocation = _invocation("expand", output_features=["value"]).__replace__(
        fragment_identifiers=["plant", "series"]
    )
    fragment = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(),
        invocation,
        lambda: pl.LazyFrame({"series": ["s1"], "value": [90.0]}),
        validate=True,
    )
    assert fragment.dimensions == ("series",)
    assert fragment.dataframe.collect().columns == ["series", "value"]


def test_expand_fragment_rejects_duplicate_parent_identifiers_with_validation() -> None:
    invocation = _invocation("expand", output_features=["value"]).__replace__(
        fragment_identifiers=["series"]
    )

    with pytest.raises(ValueError, match="duplicate dimension keys"):
        fragment_module.Fragment.stage(
            backend_module.PolarsBackend(),
            invocation,
            lambda: pl.LazyFrame({"series": ["s1", "s1"], "value": [90.0, 80.0]}),
            validate=True,
        )


def test_expand_fragment_can_still_return_the_complete_target_grain() -> None:
    invocation = _invocation("expand", output_features=["value"]).__replace__(
        fragment_identifiers=["series"]
    )
    frame = pl.LazyFrame({"key": ["p1", "p2"], "value": [90.0, 80.0]})

    fragment = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(), invocation, lambda: frame, validate=True
    )

    assert fragment.dimensions == ("key",)
    assert fragment.dataframe.collect().equals(frame.collect())


def test_full_grain_fragment_retains_other_resolution_keys_without_changing_uniqueness() -> None:
    invocation = _invocation("expand", output_features=["value"]).__replace__(
        fragment_identifiers=["key", "series"]
    )
    frame = pl.LazyFrame({"key": ["p1", "p2"], "series": ["s1", "s1"], "value": [90.0, 80.0]})
    backend = backend_module.PolarsBackend()

    fragment = fragment_module.Fragment.stage(backend, invocation, lambda: frame, validate=True)

    assert fragment.dimensions == ("key",)
    assert (
        fragment.dataframe.collect().select(frame.collect_schema().names()).equals(frame.collect())
    )
    with pytest.raises(ValueError, match="duplicate dimension keys"):
        fragment_module.Fragment.stage(
            backend,
            invocation,
            lambda: frame.with_columns(pl.lit("p1").alias("key")),
            validate=True,
        )


@pytest.mark.parametrize("resource", ["fragment", "dataset"])
def test_missing_dimension_log_identifies_resource_before_failure(
    resource: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="uptimely.engine.dataframe")
    backend = backend_module.PolarsBackend()
    frame = pl.DataFrame({"value": [1]})
    invocation = _invocation()

    with pytest.raises(ValueError, match="missing dimension columns: key"):
        if resource == "fragment":
            fragment_module.Fragment(frame, ("key",), invocation).validate_invocation_result(
                backend, invocation
            )
        else:
            dataset_module.Dataset(backend, ["key"], frame).validate_accumulated_frame(
                description="Accumulated profile telemetry"
            )

    expected = f"Check {resource} required dimension columns ('key',)"
    if resource == "fragment":
        expected += (
            " from operator calculate, function calculate, invocation invocation, profile dataset"
        )
    else:
        expected += " for Accumulated profile telemetry"
    assert caplog.messages[-1] == expected


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
def test_merge_rejects_feature_collisions(lazy: bool, collision: bool) -> None:
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
            merge_module.Merge(dataset, fragment).validate_input()
    else:
        merge_module.Merge(dataset, fragment).validate_input()


@pytest.mark.parametrize(
    ("result", "dataset", "fragment_frame", "message"),
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
def test_merge_checks_complete_result_schema(
    result: pl.DataFrame,
    dataset: pl.DataFrame | None,
    fragment_frame: pl.DataFrame,
    message: str,
) -> None:
    backend = backend_module.PolarsBackend()
    dataset = dataset_module.Dataset(backend, ["key"], dataset)
    fragment = fragment_module.Fragment(fragment_frame, ("key",))

    with pytest.raises(ValueError, match=message):
        merge_module.Merge(dataset, fragment).validate_result(result)


def test_merge_skips_optional_checks_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = backend_module.PolarsBackend()
    dataset = dataset_module.Dataset(backend, ["key"])
    result = pl.DataFrame({"key": ["A", "A"], "value": ["wrong", "wrong"]})
    fragment = fragment_module.Fragment(
        pl.DataFrame({"key": ["A"], "value": ["wrong"]}),
        ("key",),
    )

    def unexpected_check(*args: object, **kwargs: object) -> object:
        pytest.fail("Optional candidate checks must be skipped when validation is disabled")

    monkeypatch.setattr(backend, "row_count", unexpected_check)
    monkeypatch.setattr(backend, "is_duplicated", unexpected_check)
    monkeypatch.setattr(backend, "validate_types", unexpected_check)
    merge_module.Merge(dataset, fragment).validate_result(result)


def test_executor_checks_vectorized_contract_and_preservation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=execution_module.__name__)
    invocation = _invocation(
        "vectorize", output_features=["new"], column_types={"key": "string", "new": "integer"}
    )
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
    context = (
        "target transform result from operator calculate, function calculate, "
        "invocation invocation, profile dataset"
    )
    assert all(context in message for message in caplog.messages)
    assert f"Check required dimension columns ['key'] for {context}" in caplog.messages
    assert f"Check declared output columns ['new'] exist in {context}" in caplog.messages
    assert (
        "Check output columns ['new'] do not replace existing feature columns ['value'] "
        f"in {context}" in caplog.messages
    )
    assert f"Check existing columns ['key', 'value'] remain present in {context}" in caplog.messages
    assert (
        f"Check {context} contains no columns outside existing and declared outputs "
        "['key', 'new', 'value']" in caplog.messages
    )
    assert (
        "Check declared types of dimension and output columns "
        f"{{'key': 'string', 'new': 'integer'}} in {context}" in caplog.messages
    )


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
    identity = "from operator calculate, function calculate, invocation invocation, profile dataset"
    assert f"Check fragment dataframe type {identity}" in caplog.messages
    assert f"Check fragment declared output columns [] {identity}" in caplog.messages
    assert f"Check fragment required dimension columns ('key',) {identity}" in caplog.messages
    assert all(identity in message for message in caplog.messages)

    caplog.clear()
    caplog.set_level(logging.DEBUG, logger=dataset_module.__name__)
    dataset_module.Dataset(
        backend_module.PolarsBackend(),
        [],
        pl.DataFrame({"value": [1]}),
    ).validate_accumulated_frame(description="Accumulated profile telemetry")
    assert (
        "Check dataset dimensionless row count is at most one for Accumulated profile telemetry"
        in caplog.messages
    )
    assert (
        "Check dataset required dimension columns () for Accumulated profile telemetry"
        in caplog.messages
    )
    assert all("Accumulated profile telemetry" in message for message in caplog.messages)
