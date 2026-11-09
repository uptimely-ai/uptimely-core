import copy
import logging

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import plan as execution_plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import state as state_module
from uptimely.library.merge import polars as merge_module


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("strict_cardinality", [False, True])
@pytest.mark.parametrize("grain", ["same", "subset", "global"])
def test_dataset_selects_merge_by_fragment_dimensions(
    lazy: bool, strict_cardinality: bool, grain: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=merge_module.__name__)
    initial = pl.DataFrame({"group": ["A", "A", "B"], "id": [1, 2, 3], "value": [10, 20, 30]})
    if grain == "same":
        contribution = pl.DataFrame({"id": [2, 4], "group": ["A", "C"], "new": [2, 4]})
        dimensions = ("id", "group")
        expected = [("A", 1, None), ("A", 2, 2), ("B", 3, None), ("C", 4, 4)]
    elif grain == "subset":
        contribution = pl.DataFrame({"group": ["A", "C"], "new": [2, 4]})
        dimensions = ("group",)
        expected = [("A", 1, 2), ("A", 2, 2), ("B", 3, None)]
    else:
        contribution = pl.DataFrame({"new": [2]})
        dimensions = ()
        expected = [("A", 1, 2), ("A", 2, 2), ("B", 3, 2)]
    left = initial.lazy() if lazy else initial
    right = contribution.lazy() if lazy else contribution
    main = execution_support.dataset(left, ["group", "id"])
    fragment = fragment_module.Fragment(right, dimensions)

    projected = main.merge(
        fragment,
        join_cardinality="1:1" if strict_cardinality else "m:m",
        broadcast_cardinality="m:1" if strict_cardinality else "m:m",
    )

    result = main.dataframe.collect() if lazy else main.dataframe
    assert projected is fragment
    assert result.sort("group", "id").select("group", "id", "new").rows() == expected
    assert initial.height == 3
    assert "new" not in initial.columns
    if grain == "same":
        expected_log = (
            f"Full join on ('group', 'id') (cardinality {'1:1' if strict_cardinality else 'm:m'})"
        )
    elif grain == "subset":
        expected_log = (
            f"Left join on ('group',) (cardinality {'m:1' if strict_cardinality else 'm:m'})"
        )
    else:
        expected_log = "Cross join (dimensionless broadcast)"
    assert caplog.messages == [expected_log]


@pytest.mark.parametrize("lazy", [False, True])
def test_dataset_adopts_first_fragment(lazy: bool, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=merge_module.__name__)
    data = pl.DataFrame({"id": [1], "value": [2]})
    frame = data.lazy() if lazy else data
    main = execution_support.dataset(None, ["id"])
    fragment = fragment_module.Fragment(frame, ("id",))

    assert main.merge(fragment) is fragment
    assert main.dataframe is frame
    assert caplog.messages == ["Initialize from fragment (no join)"]


@pytest.mark.parametrize("dimensions", [(), ("other",)])
def test_dataset_rejects_unassemblable_dimensions_without_mutation(
    dimensions: tuple[str, ...],
) -> None:
    main = execution_support.dataset(None, ["id"])
    fragment = fragment_module.Fragment(pl.DataFrame({"other": [1], "value": [2]}), dimensions)

    with pytest.raises(ValueError, match="requires the accumulated|must be a subset"):
        main.merge(fragment)
    assert main.dataframe is None


@pytest.mark.parametrize("invalid", ["duplicates", "collision"])
def test_runtime_validation_failure_does_not_replace_accumulator(invalid: str) -> None:
    initial = pl.DataFrame({"id": [1], "value": [2]})
    main = execution_support.dataset(initial, ["id"])
    contribution = (
        pl.DataFrame({"id": [1, 1], "new": [3, 4]})
        if invalid == "duplicates"
        else pl.DataFrame({"id": [1], "value": [3]})
    )
    with pytest.raises(ValueError, match="duplicate dimension keys|overlap"):
        execution_support.merge_fragment(
            main,
            fragment_module.Fragment(contribution, ("id",)),
            dimension_types={"id": "integer"},
        )
    assert main.dataframe is initial
    assert main.fragments == {}


def test_fragment_preserves_raw_data_until_validation_and_projects_declared_outputs() -> None:
    data = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [3]})
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    invocation = plan.invocations[0]
    main = execution_support.dataset(None, ["asset_id"])
    fragment = fragment_module.Fragment(data, main.id_columns, invocation)

    projected = execution_support.merge_fragment(main, fragment)

    assert fragment.dataframe is data
    assert "extra" in fragment.dataframe.columns
    assert main.dataframe.columns == ["asset_id", "reading"]
    assert projected.dataframe is main.dataframe
    assert projected.invocation is invocation
    assert main.fragments == {invocation.operator_id: projected}


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("validate", [False, True])
def test_fragment_stage_loads_once_and_returns_merge_ready_data(
    monkeypatch: pytest.MonkeyPatch, lazy: bool, validate: bool
) -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    invocation = plan.invocations[0]
    backend = backend_module.PolarsBackend()
    data = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [3]})
    raw = data.lazy() if lazy else data
    events: list[str] = []
    validate_fragment = fragment_module.Fragment.validate_invocation_result

    def load() -> object:
        events.append("load")
        return raw

    def check_raw(
        fragment_validator: fragment_module.Fragment,
        backend: backend_module.DataFrameBackend,
        invocation: execution_plan.Invocation,
        *,
        output_features: list[str] | None = None,
        comparison_frame: object | None = None,
        validate_content: bool = True,
    ) -> None:
        events.append("validate")
        assert fragment_validator.dataframe is raw
        assert "extra" in backend.column_names(fragment_validator.dataframe)
        validate_fragment(
            fragment_validator,
            backend,
            invocation,
            output_features=output_features,
            comparison_frame=comparison_frame,
            validate_content=validate_content,
        )

    monkeypatch.setattr(
        fragment_module.Fragment,
        "validate_invocation_result",
        check_raw,
    )
    staged = fragment_module.Fragment.stage(backend, invocation, load, validate=validate)

    assert events == ["load", "validate"]
    assert staged.dimensions == ("asset_id",)
    assert staged.invocation is invocation
    assert backend.column_names(staged.dataframe) == ["asset_id", "reading"]
    assert backend.column_names(raw) == ["asset_id", "reading", "extra"]
    main = dataset_module.Dataset(backend, invocation.target_grain_keys)
    assert main.merge(staged) is staged
    result = main.dataframe.collect() if lazy else main.dataframe
    assert result.to_dicts() == [{"asset_id": "A", "reading": 2}]


def test_fragment_stage_propagates_loader_failure() -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")

    def load() -> object:
        raise RuntimeError("source unavailable")

    with pytest.raises(RuntimeError, match="source unavailable"):
        fragment_module.Fragment.stage(
            backend_module.PolarsBackend(),
            plan.invocations[0],
            load,
        )


@pytest.mark.parametrize(
    ("dataframe", "message"),
    [
        (object(), "must return a Polars DataFrame or LazyFrame"),
        (pl.DataFrame({"reading": [2]}), "missing dimension columns: asset_id"),
        (pl.DataFrame({"asset_id": ["A"]}), "missing output columns: reading"),
    ],
)
def test_fragment_stage_checks_structure_when_validation_is_disabled(
    dataframe: object, message: str
) -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")

    with pytest.raises(ValueError, match=message):
        fragment_module.Fragment.stage(
            backend_module.PolarsBackend(),
            plan.invocations[0],
            lambda: dataframe,
        )


@pytest.mark.parametrize("result", ["none", "target"])
def test_fragment_stage_rejects_non_fragment_invocations_without_loading(
    result: str,
) -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    invocation = copy.replace(plan.invocations[0], result=result)

    def load() -> object:
        pytest.fail("A non-dataframe invocation must not be loaded during staging")

    with pytest.raises(ValueError, match="must declare a fragment-producing compute result"):
        fragment_module.Fragment.stage(
            backend_module.PolarsBackend(),
            invocation,
            load,
        )


def test_fragment_stage_does_not_collect_lazy_result_without_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    raw = pl.LazyFrame({"asset_id": ["A"], "reading": [2], "extra": [3]})

    def unexpected_collect(*args: object, **kwargs: object) -> object:
        pytest.fail("Normal staging must preserve lazy execution")

    monkeypatch.setattr(pl.LazyFrame, "collect", unexpected_collect)
    staged = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(),
        plan.invocations[0],
        lambda: raw,
    )

    assert isinstance(staged.dataframe, pl.LazyFrame)
    assert staged.dataframe.collect_schema().names() == ["asset_id", "reading"]


def test_dataset_requires_only_physical_id_columns() -> None:
    columns = ["asset_id"]
    data = pl.DataFrame({"asset_id": [1], "reading": [2], "extra": [3]})
    main = dataset_module.Dataset(backend_module.PolarsBackend(), columns)
    columns.append("other")
    fragment = fragment_module.Fragment(data, ("asset_id",))

    assert main.id_columns == ("asset_id",)
    assert not hasattr(main, "dataset")
    assert not hasattr(main, "validator")
    assert main.merge(fragment, fragment_id="source") is fragment
    assert main.dataframe is data
    assert main.fragments == {"source": fragment}


def test_dataset_does_not_interpret_invocation_outputs_or_ids() -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    data = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [3]})
    main = execution_support.dataset(None, ["asset_id"])
    fragment = fragment_module.Fragment(data, ("asset_id",), plan.invocations[0])

    assert main.merge(fragment) is fragment
    assert main.dataframe is data
    assert main.dataframe.columns == ["asset_id", "reading", "extra"]
    assert main.fragments == {}


@pytest.mark.parametrize("subset", [False, True])
def test_failed_physical_join_preserves_dataframe_and_retained_fragment(subset: bool) -> None:
    initial = pl.DataFrame({"id": [1], "group": ["A"], "value": [2]})
    main = execution_support.dataset(None, ["id", "group"])
    retained = fragment_module.Fragment(initial, ("id", "group"))
    main.merge(retained, fragment_id="source")
    contribution = pl.DataFrame({"id": [1, 1], "group": ["A", "A"], "new": [3, 4]})
    if subset:
        contribution = contribution.drop("id")
    fragment = fragment_module.Fragment(contribution, ("group",) if subset else ("id", "group"))

    with pytest.raises(pl.exceptions.ComputeError, match="validation"):
        main.merge(
            fragment,
            fragment_id="source",
            join_cardinality="1:1",
            broadcast_cardinality="m:1",
        )

    assert main.dataframe is initial
    assert main.fragments == {"source": retained}


def test_runtime_validation_uses_column_types_from_invocation() -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    main = execution_support.dataset(None, ["asset_id"])

    fragment = fragment_module.Fragment(
        pl.DataFrame({"asset_id": [1], "reading": [2]}),
        main.id_columns,
        plan.invocations[0],
    )
    with pytest.raises(ValueError, match="expected string"):
        execution_support.merge_fragment(main, fragment)
    assert main.dataframe is None
    assert main.fragments == {}


def test_runtime_bindings_unwrap_dataset_and_fragment() -> None:
    data = pl.DataFrame({"id": [1], "value": [2]})
    main = execution_support.dataset(None, ["id"])
    projected = main.merge(fragment_module.Fragment(data, ("id",)))
    main.fragments["source"] = projected
    state = state_module.RuntimeState(datasets={"dataset": main})
    bindings = bindings_module.RuntimeBindings(state, {})

    assert bindings.resolve_value("dataset", "dataframe") is data
    assert bindings.resolve_value("source", "dataframe") is data


def test_fragment_dimension_policy_uses_carried_keys_for_expand() -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    invocation = copy.replace(
        plan.invocations[0],
        fragment_dimensions="subset",
        output_features=["new"],
        target_grain_keys=["group", "id"],
        fragment_identifiers=["group"],
    )
    frame = pl.LazyFrame({"group": ["A"], "new": [1]})
    fragment = fragment_module.Fragment.stage(
        backend_module.PolarsBackend(),
        invocation,
        lambda: frame,
    )

    assert fragment.dimensions == ("group",)
    assert fragment.dataframe.collect().to_dicts() == [{"group": "A", "new": 1}]


def test_failed_merge_preserves_retained_fragments_and_other_datasets() -> None:
    plan = execution_plan.from_json("tests/fixtures/plans/simple_engine.json")
    invocation = plan.invocations[0]
    main = execution_support.dataset(None, ["asset_id"])
    other = execution_support.dataset(None)
    valid = pl.DataFrame({"asset_id": ["A"], "reading": [1]})
    retained = execution_support.merge_fragment(
        main,
        fragment_module.Fragment(valid, main.id_columns, invocation),
    )
    accumulated = main.dataframe
    invalid = pl.DataFrame({"asset_id": ["A", "A"], "reading": [2, 3]})

    with pytest.raises(ValueError, match="duplicate dimension keys"):
        execution_support.merge_fragment(
            main,
            fragment_module.Fragment(invalid, main.id_columns, invocation),
        )

    assert main.dataframe is accumulated
    assert main.fragments == {invocation.operator_id: retained}
    assert other.fragments == {}
    assert other.fragments is not main.fragments
