"""Verify the example's provisional operator cases against compiled bindings."""

import datetime
import json
import typing
from collections import abc

import polars as pl
import polars.testing
from support import examples as example_support

from uptimely import plan
from uptimely.codebase.python import codebase, entrypoint
from uptimely.engine.runtime import execution, state
from uptimely.project import python_imports

CASE_DIR = example_support.REPOSITORY_ROOT / "example" / "tests" / "uptimely"


def _records(frame: pl.DataFrame) -> list[dict[str, object]]:
    def encode(value: object) -> str:
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        raise TypeError(f"Unsupported fixture value: {type(value).__name__}")

    return json.loads(json.dumps(frame.to_dicts(), default=encode))


def _assert_records(actual: list[dict[str, object]], expected: list[dict[str, object]]) -> None:
    if not expected:
        assert actual == []
        return
    pl.testing.assert_frame_equal(
        pl.DataFrame(actual),
        pl.DataFrame(expected),
        check_dtypes=False,
        check_column_order=False,
    )


def test_example_operator_cases(example_bundle_factory: example_support.BundleFactory) -> None:
    bundle = example_bundle_factory()
    files = {path.stem: path for path in CASE_DIR.glob("*.json")}
    assert set(files) == set(bundle.spec_definition.profiles)
    entries = codebase.Codebase.from_locations(
        bundle.execution_plan.entrypoints, entrypoint_type=entrypoint.Entrypoint
    ).entrypoints_index
    with python_imports.expose(bundle.project_root, src_path=bundle.source_path):
        for profile_id, path in files.items():
            suite = json.loads(path.read_text(encoding="utf-8"))
            invocations = [
                invocation
                for invocation in bundle.execution_plan.invocations
                if invocation.semantics is not None
                and invocation.semantics.profile_id == profile_id
                and invocation.semantics.role == "compute"
                and bundle.spec_definition.functions.root[invocation.semantics.function_id].category
                not in {"read", "write", "workflow"}
            ]
            invocations_by_operator = {
                invocation.semantics.operator_id: invocation
                for invocation in invocations
                if invocation.semantics is not None
            }
            assert len(invocations_by_operator) == len(invocations)
            assert set(suite) == set(invocations_by_operator)
            for operator_id, operator in suite.items():
                assert operator["cases"], (profile_id, operator_id)
                for case in operator["cases"].values():
                    _run_case(invocations_by_operator[operator_id], case, entries)


def _run_case(
    invocation: plan.Invocation,
    case: dict[str, typing.Any],
    entries: abc.Mapping[str, entrypoint.Entrypoint],
) -> None:
    runtime = state.RuntimeState()
    inputs = case["inputs"]
    for argument, value in invocation.arguments.items():
        if isinstance(value, str) and value.startswith(plan.Variable.PREFIXES):
            assert argument in inputs
            runtime.store(value, pl.DataFrame(inputs[argument]).lazy())
        elif isinstance(value, str) and value.startswith("$paths."):
            raise AssertionError(f"Unexpected file argument: {argument}")
    dataframe_arguments = {
        argument
        for argument, value in invocation.arguments.items()
        if isinstance(value, str) and value.startswith(plan.Variable.PREFIXES)
    }
    assert set(inputs) == dataframe_arguments
    executor = execution.InvocationExecutor(entries, {}, runtime)
    result = executor.execute(invocation, executor.resolve_arguments(invocation))
    if isinstance(result, pl.LazyFrame):
        _assert_records(_records(result.collect()), case["expected"]["return"])
    else:
        assert result == case["expected"]["return"]
