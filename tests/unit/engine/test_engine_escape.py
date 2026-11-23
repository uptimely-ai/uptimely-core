import collections.abc
import copy
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler as uptimely_compiler
from uptimely import plan as uptimely_plan
from uptimely import spec
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.library.merge import polars as merge_module
from uptimely.plan import serialization as plan_serialization
from uptimely.spec.python import assembly, dimension, profile, ref


def _patch_callables(monkeypatch: pytest.MonkeyPatch, callables: dict[str, object]) -> None:
    def merge_by_grain_entrypoint(
        dataset: merge_module.DataFrame | None,
        fragment: merge_module.DataFrame,
        dataset_identifiers: collections.abc.Sequence[str],
        fragment_keys: collections.abc.Sequence[str] | None = None,
        *,
        key_columns: collections.abc.Sequence[str] = (),
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> merge_module.DataFrame:
        return merge_module.merge_by_grain(
            dataset,
            fragment,
            dataset_identifiers,
            fragment_keys,
            key_columns=key_columns,
            join_cardinality=join_cardinality,
            broadcast_cardinality=broadcast_cardinality,
        )

    callables = {
        "uptimely.library.merge.polars:merge_by_grain": merge_by_grain_entrypoint,
        **callables,
    }

    class _TestEntrypoint:
        def __init__(
            self, location: str, package: entrypoint_module.PackageOrigin | None = None
        ) -> None:
            self.location = location
            self.package = package
            self.module = types.SimpleNamespace(location=location.split(":", 1)[0])

        @property
        def function(self) -> object:
            return self

        def load(self) -> object:
            return callables[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", _TestEntrypoint)


@pytest.mark.parametrize(
    "return_value",
    [
        None,
        42,
        object(),
        {"non_serializable": object()},
        pl.DataFrame({"unrelated": [1]}),
    ],
)
def test_escape_ignores_any_return_without_materializing_features(
    return_value: object,
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    invocation_id = "invocation:escape:external_operator:asset:external:operator"
    escape = uptimely_plan.Invocation(
        id=invocation_id,
        entrypoint="test:escape",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="external_operator",
            operator_id="operator",
            profile_id="external",
            output_features=[],
            input_features=["external_input"],
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[escape],
        stages=[[invocation_id]],
    )
    _patch_callables(monkeypatch, {"test:escape": lambda: return_value})
    engine = engine_for_plan(plan)

    result = engine.run()

    assert result.invocation_statuses == {invocation_id: "succeeded"}
    assert result.failures == {}
    assert result.datasets == {}
    assert result.calculated_outputs == {}


def test_escape_feature_outputs_order_invocations_without_materializing_dataframes(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    calls: list[str] = []

    def first() -> int:
        calls.append("first")
        return 17

    def second() -> object:
        calls.append("second")
        return object()

    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        entrypoint="test:first",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="first",
            operator_id="first",
            profile_id="external",
            output_features=["first_output"],
            input_features=["external_input"],
        ),
    )
    second_invocation = uptimely_plan.Invocation(
        id=second_id,
        entrypoint="test:second",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="second",
            operator_id="second",
            profile_id="external",
            output_features=[],
            input_features=["first_output"],
            dependency_ids=[first_id],
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    _patch_callables(monkeypatch, {"test:first": first, "test:second": second})
    result = engine_for_plan(plan).run()

    assert calls == ["first", "second"]
    assert result.invocation_statuses == {first_id: "succeeded", second_id: "succeeded"}
    assert result.failures == {}
    assert result.datasets == {}
    assert result.calculated_outputs == {}


def test_escape_resolves_literal_and_runtime_arguments(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    invocation_id = "invocation:escape:external_operator:asset:external:operator"
    escape = uptimely_plan.Invocation(
        id=invocation_id,
        entrypoint="test:escape",
        arguments={"path": "$params.output", "mode": "replace"},
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="external_operator",
            operator_id="operator",
            profile_id="external",
            output_features=[],
            input_features=["external_input"],
            argument_types={"path": "string", "mode": "string"},
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[escape],
        stages=[[invocation_id]],
    )
    received: list[tuple[str, str]] = []

    def external_operator(path: str, mode: str) -> None:
        received.append((path, mode))

    _patch_callables(monkeypatch, {"test:escape": external_operator})
    result = engine_for_plan(plan, {"output": "/tmp/external-output.csv"}).run()

    assert received == [("/tmp/external-output.csv", "replace")]
    assert result.invocation_statuses == {invocation_id: "succeeded"}
    assert result.failures == {}


def test_escape_missing_explicit_dataframe_argument_fails_and_skips_downstream(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        entrypoint="test:first",
        arguments={"frame": "missing"},
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="first",
            operator_id="first",
            profile_id="external",
            output_features=[],
            input_features=["external_input"],
            argument_types={"frame": "dataframe"},
        ),
    )
    second_invocation = copy.replace(
        first_invocation,
        id=second_id,
        entrypoint="test:second",
        semantics=copy.replace(
            first_invocation.semantics,
            function_id="second",
            operator_id="second",
            output_features=[],
            dependency_ids=[first_id],
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    _patch_callables(monkeypatch, {"test:first": lambda **_: None, "test:second": lambda **_: None})
    result = engine_for_plan(plan).run()

    assert result.invocation_statuses == {first_id: "failed", second_id: "skipped"}
    assert "Profile dataframe is unavailable: missing" in result.failures[first_id]


def test_escape_outputs_are_not_passed_to_following_dataframe_invocations(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    read_id = "invocation:read:load:asset:telemetry:load"
    merge_id = "invocation:merge:combine:asset:telemetry:load"
    escape_id = "invocation:escape:external_operator:asset:telemetry:operator"
    vectorize_id = "invocation:vectorize:consume:asset:telemetry:consume"
    observed: list[pl.DataFrame] = []

    def read() -> pl.DataFrame:
        return pl.DataFrame({"asset_id": ["A"], "reading": [3]})

    def external_operator(dataset: pl.DataFrame) -> pl.DataFrame:
        observed.append(dataset)
        return pl.DataFrame({"external_result": [4]})

    def consume() -> pl.DataFrame:
        pytest.fail("The dataframe operator must not run without its declared input feature")

    read_invocation = uptimely_plan.Invocation(
        id=read_id,
        entrypoint="test:read",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="fragment",
            fragment_dimensions="target",
            function_id="load",
            operator_id="load",
            profile_id="telemetry",
            output_features=["asset_id", "reading"],
        ),
    )
    merge_invocation = uptimely_plan.Invocation(
        id=merge_id,
        entrypoint="test:merge",
        arguments={
            "dataset": "telemetry",
            "fragment": "$operators.@.fragment",
            "dataset_identifiers": ["asset_id"],
        },
        semantics=uptimely_plan.InvocationSemantics(
            role="merge",
            result="target",
            function_id="combine",
            operator_id="load",
            profile_id="telemetry",
            target_identifiers=["asset_id"],
            argument_types={
                "dataset": "dataframe | null",
                "fragment": "dataframe",
                "dataset_identifiers": "array[string]",
            },
            dependency_ids=[read_id],
        ),
    )
    escape_invocation = uptimely_plan.Invocation(
        id=escape_id,
        entrypoint="test:escape",
        arguments={"dataset": "telemetry"},
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="external_operator",
            operator_id="external_result",
            profile_id="telemetry",
            output_features=["external_result"],
            input_features=["reading"],
            argument_types={"dataset": "dataframe"},
            dependency_ids=[merge_id],
        ),
    )
    vectorize_invocation = uptimely_plan.Invocation(
        id=vectorize_id,
        entrypoint="test:consume",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="target",
            dataframe_input_scope="target",
            function_id="consume",
            operator_id="consume",
            profile_id="telemetry",
            output_features=["processed"],
            input_features=["external_result"],
            dependency_ids=[escape_id],
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[read_invocation, merge_invocation, escape_invocation, vectorize_invocation],
        stages=[[read_id], [merge_id], [escape_id], [vectorize_id]],
    )

    _patch_callables(
        monkeypatch,
        {
            "test:read": read,
            "test:escape": external_operator,
            "test:consume": consume,
            "test:merge": merge_module.merge_by_grain,
        },
    )
    result = engine_for_plan(plan).run(validate=True)

    assert result.invocation_statuses == {
        read_id: "succeeded",
        merge_id: "succeeded",
        escape_id: "succeeded",
        vectorize_id: "failed",
    }
    assert (
        "input feature is unavailable or ambiguous: external_result"
        in result.failures[vectorize_id]
    )
    assert observed[0].to_dicts() == result.datasets["telemetry"].to_dicts()
    assert "external_result" not in result.datasets["telemetry"].columns
    assert result.calculated_outputs == {}


def test_escape_exception_fails_and_skips_downstream(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    first_id = "invocation:escape:first:asset:external:first"
    second_id = "invocation:escape:second:asset:external:second"
    first_invocation = uptimely_plan.Invocation(
        id=first_id,
        entrypoint="test:first",
        semantics=uptimely_plan.InvocationSemantics(
            role="compute",
            result="none",
            function_id="first",
            operator_id="first",
            profile_id="external",
            output_features=[],
            input_features=["external_input"],
        ),
    )
    second_invocation = copy.replace(
        first_invocation,
        id=second_id,
        entrypoint="test:second",
        semantics=copy.replace(
            first_invocation.semantics,
            function_id="second",
            operator_id="second",
            output_features=[],
            dependency_ids=[first_id],
        ),
    )
    plan = uptimely_plan.ExecutionPlan(
        plan_version=uptimely_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[first_invocation, second_invocation],
        stages=[[first_id], [second_id]],
    )

    def fail() -> None:
        raise RuntimeError("external operator failed")

    _patch_callables(monkeypatch, {"test:first": fail, "test:second": lambda: None})
    result = engine_for_plan(plan).run()

    assert result.invocation_statuses == {first_id: "failed", second_id: "skipped"}
    assert result.failures == {first_id: "external operator failed"}


def test_python_spec_escape_executes_after_json_plan_reload_with_local_storage(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    source_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    plan_path = tmp_path / "execution_plan.json"
    source_path.write_text("asset_id,value\nA,2\nB,3\n", encoding="utf-8")
    package_name = f"engine_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "external_operator.py").write_text(
        "import polars as pl\n"
        f"SOURCE = {str(source_path)!r}\n"
        f"OUTPUT = {str(output_path)!r}\n"
        "def process() -> None:\n"
        "    frame = pl.read_csv(SOURCE)\n"
        "    result = frame.with_columns((pl.col('value') * 2).alias('external_result'))\n"
        "    result.write_csv(OUTPUT)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    declaration = profile.Profile(
        id="external",
        grain=[
            dimension.Dimension(
                id="asset",
                resolutions=[dimension.Resolution(id="asset", key="asset_id", type="string")],
            ).resolution("asset"),
        ],
        assembly=[
            assembly.Operator(
                id="external_operator",
                inputs=[],
                outputs=[],
                compute=assembly.Bind(
                    ref.function(f"{package_name}.external_operator:process", returns="any"),
                ),
            )
        ],
    )
    spec_definition = spec.from_python(profiles=[declaration])

    compiled = uptimely_compiler.Compiler().compile(spec_definition)
    plan_serialization.export_json(compiled, plan_path)
    restored = uptimely_plan.from_json(plan_path)
    result = engine_for_plan(restored, project_root=tmp_path).run()

    assert result.failures == {}
    assert result.invocation_statuses == {compiled.invocations[0].id: "succeeded"}
    assert result.datasets == {}
    assert result.calculated_outputs == {}
    assert pl.read_csv(output_path).rows() == [("A", 2, 4), ("B", 3, 6)]
