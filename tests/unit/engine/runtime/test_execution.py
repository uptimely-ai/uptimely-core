import pathlib
from collections import abc

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import engine, plan, spec
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.engine.runtime import state as state_module
from uptimely.library.merge import polars as merge_module


def _patch_entrypoints(
    monkeypatch: pytest.MonkeyPatch, functions: dict[str, abc.Callable[..., object]]
) -> None:
    class TestEntrypoint:
        def __init__(self, location: str) -> None:
            self.location = location

        def load(self) -> abc.Callable[..., object]:
            return functions[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", TestEntrypoint)


def test_runs_explicit_calls_in_stage_order_with_nested_references(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    tmp_path: pathlib.Path,
) -> None:
    calls: list[str] = []
    raw = pl.DataFrame({"id": [1], "feature": [2], "extra": [3]})

    def read(path: str, label: str) -> pl.DataFrame:
        calls.append("read")
        assert path == str(tmp_path / "input.csv")
        assert label == "literal"
        return raw

    def none() -> None:
        calls.append("none")
        return

    def compute(data: dict[str, object]) -> pl.DataFrame:
        calls.append("compute")
        assert data == {
            "frames": [raw, None],
            "parameter": 7,
            "absolute": str(tmp_path / "absolute.csv"),
        }
        return raw.with_columns((pl.col("feature") * 2).alias("output"))

    def write(dataset: pl.DataFrame) -> None:
        calls.append("write")
        assert dataset.columns == ["id", "feature", "extra", "output"]

    _patch_entrypoints(
        monkeypatch,
        {"test:read": read, "test:none": none, "test:compute": compute, "test:write": write},
    )
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "write",
                    "entrypoint": "test:write",
                    "arguments": {"dataset": "$dataset.pump.merge"},
                    "returns": None,
                },
                {
                    "id": "compute",
                    "entrypoint": "test:compute",
                    "arguments": {
                        "data": {
                            "frames": ["$fragments.pump.read", "$datasets.pump.none"],
                            "parameter": "$params.limit",
                            "absolute": "$paths.absolute",
                        }
                    },
                    "returns": "$dataset.pump.merge",
                },
                {
                    "id": "none",
                    "entrypoint": "test:none",
                    "arguments": {},
                    "returns": "$datasets.pump.none",
                },
                {
                    "id": "read",
                    "entrypoint": "test:read",
                    "arguments": {"path": "$paths.input", "label": "literal"},
                    "returns": "$fragments.pump.read",
                },
            ],
            "stages": [["read", "none"], ["compute", "write"]],
            "datasets": {"pump": "$dataset.pump.merge", "also_pump": "$dataset.pump.merge"},
        }
    )
    instance = engine.Engine(
        bundle_for_plan(saved, project_root=tmp_path, spec_definition=spec.Spec()),
        parameters={"limit": 7},
        paths={"input": "input.csv", "absolute": str(tmp_path / "absolute.csv")},
    )

    result = instance.run()

    assert calls == ["read", "none", "compute", "write"]
    assert not result.failures
    assert result.calculated_outputs is None
    assert all(status == "succeeded" for status in result.invocation_statuses.values())
    assert result.datasets["pump"] is result.datasets["also_pump"]
    assert result.datasets["pump"].to_dicts() == [{"id": 1, "feature": 2, "extra": 3, "output": 4}]


def test_merge_receives_explicit_relation_keys(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    target = pl.DataFrame({"pump": ["p1", "p2"], "series": ["s1", "s2"]})
    fragment = pl.DataFrame({"series": ["s1", "s2"], "capacity": [10, 20]})
    _patch_entrypoints(
        monkeypatch,
        {
            "test:target": lambda: target,
            "test:fragment": lambda: fragment,
            "uptimely.library.merge.polars:merge_by_grain": merge_module.merge_by_grain,
        },
    )
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "target",
                    "entrypoint": "test:target",
                    "arguments": {},
                    "returns": "$datasets.pump.target",
                },
                {
                    "id": "fragment",
                    "entrypoint": "test:fragment",
                    "arguments": {},
                    "returns": "$fragments.pump.capacity",
                },
                {
                    "id": "merge",
                    "entrypoint": "uptimely.library.merge.polars:merge_by_grain",
                    "arguments": {
                        "dataset": "$datasets.pump.target",
                        "fragment": "$fragments.pump.capacity",
                        "dataset_identifiers": ["pump"],
                        "key_columns": ["series"],
                    },
                    "returns": "$dataset.pump.capacity",
                },
            ],
            "stages": [["target", "fragment", "merge"]],
            "datasets": {"pump": "$dataset.pump.capacity"},
        }
    )

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run()

    assert not result.failures
    frame = result.datasets["pump"]
    assert isinstance(frame, pl.DataFrame)
    assert frame.to_dicts() == [
        {"pump": "p1", "series": "s1", "capacity": 10},
        {"pump": "p2", "series": "s2", "capacity": 20},
    ]


def test_loads_real_entrypoints_and_records_dataframe_preview(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "read",
                    "entrypoint": "support.functions:read_observation_totals",
                    "arguments": {},
                    "returns": "$datasets.pump.read",
                },
                {
                    "id": "calculate",
                    "entrypoint": "support.functions:sum_observation_features",
                    "arguments": {
                        "dataset": "$datasets.pump.read",
                        "left_feature": "input_1",
                        "right_feature": "input_2",
                        "output": "total",
                    },
                    "returns": "$datasets.pump.total",
                },
            ],
            "stages": [["read"], ["calculate"]],
            "datasets": {"pump": "$datasets.pump.total"},
        }
    )

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run()

    assert not result.failures
    preview = result.preview_frames["pump"]
    assert isinstance(preview, pl.DataFrame)
    assert preview["total"].to_list() == [3, 7]


def test_failure_stops_execution_and_preserves_completed_aliases(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    calls: list[str] = []

    def fail(value: object) -> object:
        calls.append("fail")
        raise ValueError("broken call")

    def after() -> None:
        calls.append("after")

    _patch_entrypoints(
        monkeypatch, {"test:read": lambda: 5, "test:fail": fail, "test:after": after}
    )
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "read",
                    "entrypoint": "test:read",
                    "arguments": {},
                    "returns": "$datasets.pump.read",
                },
                {
                    "id": "fail",
                    "entrypoint": "test:fail",
                    "arguments": {"value": "$datasets.pump.read"},
                    "returns": "$dataset.pump.fail",
                },
                {"id": "after", "entrypoint": "test:after", "arguments": {}, "returns": None},
            ],
            "stages": [["read", "fail", "after"]],
            "datasets": {"complete": "$datasets.pump.read", "incomplete": "$dataset.pump.fail"},
        }
    )

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run()

    assert calls == ["fail"]
    assert result.datasets == {"complete": 5}
    assert result.invocation_statuses == {"read": "succeeded", "fail": "failed", "after": "skipped"}
    assert result.failures == {"fail": "broken call"}
    assert "complete" in result.preview_failures


@pytest.mark.parametrize(
    ("argument", "error"),
    [
        ("$params.missing", "Unresolved parameter: missing"),
        ("$paths.missing", "Unresolved path: missing"),
    ],
)
def test_missing_resources_fail_before_call(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    argument: str,
    error: str,
) -> None:
    calls: list[object] = []
    _patch_entrypoints(monkeypatch, {"test:call": lambda value: calls.append(value)})
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "call",
                    "entrypoint": "test:call",
                    "arguments": {"value": argument},
                    "returns": None,
                }
            ],
            "stages": [["call"]],
            "datasets": {},
        }
    )

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run()

    assert calls == []
    assert result.failures == {"call": error}


def test_state_distinguishes_none_from_missing_and_prevents_overwrite() -> None:
    state = state_module.RuntimeState()
    state.store("$datasets.pump.read", None)
    assert state.resolve("$datasets.pump.read") is None
    with pytest.raises(ValueError, match="Return is unavailable"):
        state.resolve("$datasets.pump.missing")
    with pytest.raises(ValueError, match="assigned more than once"):
        state.store("$datasets.pump.read", 1)


def test_targeted_execution_fails_before_execution(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [],
            "stages": [],
            "datasets": {},
        }
    )
    instance = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec()))

    with pytest.raises(NotImplementedError, match="Targeted"):
        instance.run(operator=("pump", "read"))
