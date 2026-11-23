import logging
from collections import abc

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import engine, plan, spec
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.engine.dataframe import backend
from uptimely.engine.runtime import validation


def _patch_entrypoints(
    monkeypatch: pytest.MonkeyPatch, functions: dict[str, abc.Callable[..., object]]
) -> None:
    class TestEntrypoint:
        def __init__(self, location: str) -> None:
            self.location = location

        def load(self) -> abc.Callable[..., object]:
            return functions[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", TestEntrypoint)


def _semantics(operator: str, **fields: object) -> dict[str, object]:
    return {
        "role": "compute",
        "result": "target",
        "function_id": operator,
        "operator_id": operator,
        "profile_id": "pump",
        "target_identifiers": ["id"],
        "column_types": {"id": "string", "input": "integer", "output": "integer"},
        **fields,
    }


def _plan(*, input_features: list[str] | None = None) -> plan.ExecutionPlan:
    return plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {
                    "id": "read",
                    "entrypoint": "test:read",
                    "arguments": {},
                    "returns": "$datasets.pump.read",
                    "semantics": _semantics("read", output_features=["input"]),
                },
                {
                    "id": "calculate",
                    "entrypoint": "test:calculate",
                    "arguments": {"dataset": "$datasets.pump.read"},
                    "returns": "$datasets.pump.calculate",
                    "semantics": _semantics(
                        "calculate",
                        dataframe_input_scope="target",
                        argument_types={"dataset": "dataframe"},
                        input_features=["input"],
                        output_features=["output"],
                        row_count_relation="same",
                        key_relation="identical",
                        row_order_relation="preserve",
                        existing_data_relation="preserve",
                    ),
                },
                {
                    "id": "write",
                    "entrypoint": "test:write",
                    "arguments": {"dataset": "$datasets.pump.calculate"},
                    "returns": None,
                    "semantics": _semantics(
                        "write",
                        result="none",
                        is_sink=True,
                        argument_types={"dataset": "dataframe"},
                        input_features=input_features or ["output"],
                    ),
                },
            ],
            "stages": [["read"], ["calculate", "write"]],
            "datasets": {"pump": "$datasets.pump.calculate"},
        }
    )


@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize("lazy", [False, True])
def test_validation_keeps_calls_and_results_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    caplog: pytest.LogCaptureFixture,
    validate: bool,
    lazy: bool,
) -> None:
    caplog.set_level(logging.INFO, logger="uptimely.engine.engine")
    frame = pl.DataFrame({"id": ["a", "b"], "input": [1, 2]})
    source = frame.lazy() if lazy else frame
    result_frame = source.with_columns((pl.col("input") * 2).alias("output"))
    calls: list[str] = []

    def calculate(dataset: object) -> object:
        calls.append("calculate")
        assert dataset is source
        return result_frame

    def write(dataset: object) -> None:
        calls.append("write")
        assert dataset is result_frame

    _patch_entrypoints(
        monkeypatch, {"test:read": lambda: source, "test:calculate": calculate, "test:write": write}
    )
    instance = engine.Engine(bundle_for_plan(_plan(), spec_definition=spec.Spec()))

    result = instance.run(validate=validate)

    assert not result.failures
    assert result.datasets["pump"] is result_frame
    assert calls == ["calculate", "write"]
    records = [
        record.message for record in caplog.records if record.name == "uptimely.engine.engine"
    ]
    assert records == (["Analytical runtime validation enabled"] if validate else [])


@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize(
    ("violation", "message"),
    [
        ("missing", "missing output columns"),
        ("wrong_type", "expected integer"),
        ("duplicates", "duplicate identifiers"),
        ("missing_existing", "preserve existing columns"),
        ("reordered", "preserve row order"),
        ("changed", "preserve existing data"),
    ],
)
def test_output_contracts_are_checked_only_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    validate: bool,
    violation: str,
    message: str,
) -> None:
    source = pl.DataFrame({"id": ["a", "b"], "input": [1, 2]})
    result_frame = source.with_columns(pl.col("input").alias("output"))
    if violation == "missing":
        result_frame = source
    elif violation == "wrong_type":
        result_frame = source.with_columns(pl.lit("bad").alias("output"))
    elif violation == "duplicates":
        result_frame = result_frame.with_columns(pl.lit("a").alias("id"))
    elif violation == "missing_existing":
        result_frame = result_frame.drop("input")
    elif violation == "reordered":
        result_frame = result_frame.reverse()
    elif violation == "changed":
        result_frame = result_frame.with_columns((pl.col("input") + 1).alias("input"))
    calls: list[str] = []
    _patch_entrypoints(
        monkeypatch,
        {
            "test:read": lambda: source,
            "test:calculate": lambda dataset: result_frame,
            "test:write": lambda dataset: calls.append("write"),
        },
    )
    instance = engine.Engine(bundle_for_plan(_plan(), spec_definition=spec.Spec()))

    result = instance.run(validate=validate)

    if validate:
        assert message in result.failures["calculate"]
        assert result.invocation_statuses["write"] == "skipped"
        assert result.datasets == {}
        assert calls == []
    else:
        assert not result.failures
        assert result.datasets["pump"] is result_frame
        assert calls == ["write"]


def test_input_validation_precedes_sink_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    source = pl.DataFrame({"id": ["a"], "input": [1]})
    calls: list[str] = []
    _patch_entrypoints(
        monkeypatch,
        {
            "test:read": lambda: source,
            "test:calculate": lambda dataset: dataset.with_columns(pl.lit(2).alias("output")),
            "test:write": lambda dataset: calls.append("write"),
        },
    )
    instance = engine.Engine(
        bundle_for_plan(_plan(input_features=["missing"]), spec_definition=spec.Spec())
    )

    result = instance.run(validate=True)

    assert "missing input features: missing" in result.failures["write"]
    assert calls == []


@pytest.mark.parametrize("validate", [False, True])
def test_missing_semantics_fail_only_when_validation_requested(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    validate: bool,
) -> None:
    saved = plan.from_dict(
        {
            "plan_version": plan.PLAN_VERSION,
            "required_backend": "polars",
            "invocations": [
                {"id": "write", "entrypoint": "test:write", "arguments": {}, "returns": None}
            ],
            "stages": [["write"]],
            "datasets": {},
        }
    )
    calls: list[str] = []
    _patch_entrypoints(monkeypatch, {"test:write": lambda: calls.append("write")})

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run(
        validate=validate
    )

    if validate:
        assert "missing analytical semantics" in result.failures["write"]
        assert calls == []
    else:
        assert not result.failures
        assert calls == ["write"]


def test_mutated_eager_input_is_detected_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    source = pl.DataFrame({"id": ["a"], "input": [1]})

    def calculate(dataset: pl.DataFrame) -> pl.DataFrame:
        dataset.replace_column(1, pl.Series("input", [9]))
        return dataset.with_columns(pl.lit(2).alias("output"))

    _patch_entrypoints(
        monkeypatch,
        {"test:read": lambda: source, "test:calculate": calculate, "test:write": lambda **_: None},
    )
    instance = engine.Engine(bundle_for_plan(_plan(), spec_definition=spec.Spec()))

    result = instance.run(validate=True)

    assert "preserve existing data" in result.failures["calculate"]
    assert result.datasets == {}


@pytest.mark.parametrize("validate", [False, True])
@pytest.mark.parametrize("violation", ["collision", "missing_column"])
def test_merge_contracts_do_not_change_the_call(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    validate: bool,
    violation: str,
) -> None:
    target = pl.DataFrame({"id": ["a"], "input": [1]})
    fragment = pl.DataFrame({"id": ["a"], "output": [2]})
    if violation == "collision":
        fragment = fragment.with_columns(pl.lit(1).alias("input"))
    calls: list[str] = []

    def merge(dataset: pl.DataFrame, fragment: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
        calls.append("merge")
        assert dataset is target
        assert keys == ["id"]
        return fragment

    _patch_entrypoints(
        monkeypatch,
        {"test:target": lambda: target, "test:fragment": lambda: fragment, "test:merge": merge},
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
                    "semantics": _semantics("target", output_features=["input"]),
                },
                {
                    "id": "fragment",
                    "entrypoint": "test:fragment",
                    "arguments": {},
                    "returns": "$fragments.pump.fragment",
                    "semantics": _semantics(
                        "fragment",
                        result="fragment",
                        fragment_dimensions="target",
                        output_features=["output"],
                    ),
                },
                {
                    "id": "merge",
                    "entrypoint": "test:merge",
                    "arguments": {
                        "dataset": "$datasets.pump.target",
                        "fragment": "$fragments.pump.fragment",
                        "keys": ["id"],
                    },
                    "returns": "$dataset.pump.merge",
                    "semantics": _semantics(
                        "merge",
                        role="merge",
                        argument_types={"dataset": "dataframe", "fragment": "dataframe"},
                    ),
                },
            ],
            "stages": [["target", "fragment", "merge"]],
            "datasets": {"pump": "$dataset.pump.merge"},
        }
    )

    result = engine.Engine(bundle_for_plan(saved, spec_definition=spec.Spec())).run(
        validate=validate
    )

    if not validate:
        assert not result.failures
        assert result.datasets["pump"] is fragment
        assert calls == ["merge"]
    else:
        expected = "overlap" if violation == "collision" else "missing required columns"
        assert expected in result.failures["merge"]
        assert result.datasets == {}
        assert calls == ([] if violation == "collision" else ["merge"])


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("data", "error"),
    [
        ({"series": ["s1"], "output": [2], "extra": [9]}, None),
        ({"series": ["s1", "s1"], "output": [2, 3]}, "duplicate identifiers"),
        ({"series": [1], "output": [2]}, "expected string"),
        ({"series": ["s1"]}, "missing output columns"),
    ],
)
def test_subset_fragment_validation(
    lazy: bool, data: dict[str, list[object]], error: str | None
) -> None:
    invocation = plan.Invocation.model_validate(
        {
            "id": "fragment",
            "entrypoint": "test:fragment",
            "arguments": {},
            "returns": "$fragments.pump.fragment",
            "semantics": _semantics(
                "fragment",
                result="fragment",
                fragment_dimensions="subset",
                fragment_keys=["series"],
                column_types={"series": "string", "output": "integer"},
                output_features=["output"],
            ),
        }
    )
    frame: pl.DataFrame | pl.LazyFrame = pl.DataFrame(data)
    if lazy:
        frame = frame.lazy()
    validator = validation.InvocationValidator(backend.PolarsBackend())
    context = validator.before(invocation, {})

    if error is not None:
        with pytest.raises(ValueError, match=error):
            validator.after(invocation, frame, context)
    else:
        validator.after(invocation, frame, context)
        assert frame.collect_schema().names() == ["series", "output", "extra"]
