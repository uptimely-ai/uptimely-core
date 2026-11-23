import copy
import json
import pathlib

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler, engine, spec
from uptimely import plan as plan_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import model as spec_model
from uptimely.spec import serialization as spec_serialization
from uptimely.spec.python import assembly, dimension, feature, merge, profile, ref
from uptimely.spec.validation import validate_spec


def read_values(lazy: bool = False, empty: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "id": [1, 2, 3, 4],
            "value": [2, 4, 6, None],
        }
    )
    if empty:
        frame = frame.clear()
    return frame.lazy() if lazy else frame


def double(
    dataset: pl.DataFrame | pl.LazyFrame, column: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    return dataset.with_columns((pl.col(column) * 2).alias(output))


def summarize(
    dataset: pl.DataFrame | pl.LazyFrame, column: str, calculated: str
) -> pl.DataFrame | pl.LazyFrame:
    return dataset.group_by("group").agg(
        pl.col(column).max().alias("maximum"),
        pl.col(calculated).mean().alias("average"),
        pl.col(column).alias("values"),
    )


def total(dataset: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    return dataset.select(pl.col("maximum").sum().alias("total"))


def maximum(dataset: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    return dataset.select(pl.col("maximum").max().alias("global_max"))


def read_reference_constant(lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"source_value": [10.0]})
    return frame.lazy() if lazy else frame


def read_conform_target() -> pl.DataFrame:
    return pl.DataFrame({"group": ["A", "B"], "base_value": [10, 20]})


def read_conform_source() -> pl.DataFrame:
    return pl.DataFrame({"group": ["B", "C"], "source_value": [2, 3]})


def conform_source(source: pl.DataFrame, matching_keys: list[str]) -> pl.DataFrame:
    assert source.columns == ["group", "source_value"]
    assert matching_keys == ["group"]
    return source.select(*matching_keys, pl.col("source_value").alias("conformed_value"))


def merge_seeded_dataset(dataset: pl.DataFrame | None, fragment: pl.DataFrame) -> pl.DataFrame:
    assert dataset is not None
    return dataset.join(fragment, on="group", how="full", coalesce=True)


def write_seeded_dataset(dataset: pl.DataFrame, output: str) -> None:
    dataset.write_csv(output)


def _spec(*, lazy=False, empty=False):
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    identifier = dimension.Dimension(
        id="id",
        resolutions=[dimension.Resolution(id="id", key="id", type="integer")],
    )
    source = profile.Profile(
        id="observations",
        grain=[group.resolution("group"), identifier.resolution("id")],
        assembly=[
            assembly.Operator(
                id="read_values",
                inputs=[],
                outputs=[feature.Feature(id="value")],
                compute=assembly.Bind(
                    ref.function(read_values),
                    lazy=lazy,
                    empty=empty,
                ),
                merge=merge.default(),
            ),
            assembly.Operator(
                id="double",
                inputs=[ref.feature("value")],
                outputs=[feature.Feature(id="doubled")],
                compute=assembly.Bind(
                    ref.function(double),
                    dataset=ref.profile().dataset,
                    column=ref.feature("value").id,
                    output=ref.feature("doubled").id,
                ),
            ),
            assembly.Operator(
                id="unneeded",
                inputs=[ref.feature("value")],
                outputs=[feature.Feature(id="unneeded")],
                compute=assembly.Bind(
                    ref.function(double),
                    dataset=ref.profile().dataset,
                    column=ref.feature("value").id,
                    output=ref.feature("unneeded").id,
                ),
            ),
        ],
    )
    summary = profile.Profile(
        id="summary",
        grain=[group.resolution("group")],
        assembly=[
            assembly.Operator(
                id="group_summary",
                inputs=[ref.feature("value"), ref.feature("doubled")],
                outputs=[feature.Feature(id=name) for name in ("maximum", "average", "values")],
                compute=assembly.Bind(
                    ref.function(summarize),
                    dataset=ref.profile("observations").dataset,
                    column=ref.feature("value").id,
                    calculated=ref.feature("doubled").id,
                ),
                merge=merge.default(),
            )
        ],
    )
    global_summary = profile.Profile(
        id="global",
        assembly=[
            assembly.Operator(
                id="global_total",
                inputs=[ref.feature("maximum")],
                outputs=[feature.Feature(id="total")],
                compute=assembly.Bind(
                    ref.function(total),
                    dataset=ref.profile("summary").dataset,
                ),
                merge=merge.default(),
            ),
            assembly.Operator(
                id="global_maximum",
                inputs=[ref.feature("maximum")],
                outputs=[feature.Feature(id="global_max")],
                compute=assembly.Bind(
                    ref.function(maximum),
                    dataset=ref.profile("summary").dataset,
                ),
                merge=merge.default(),
            ),
        ],
    )
    return spec.from_python(
        profiles=[source, summary, global_summary],
    )


@pytest.mark.parametrize("lazy", [False, True])
def test_grouped_dataframe_outputs_execute_once_with_calculated_inputs(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _spec(lazy=lazy)
    plan = compiler.Compiler().compile(spec_definition, features=["average"])
    assert not any("unneeded" in item.semantics.output_features for item in plan.invocations)
    collapse = next(item for item in plan.invocations if item.semantics.profile_id == "summary")
    assert collapse.semantics.input_features == ["value", "doubled"]
    assert len(collapse.semantics.dependency_ids) == 2
    result = engine_for_plan(plan, spec_definition=spec_definition).run()
    assert not result.failures
    frame = result.datasets["summary"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("group").to_dicts() == [
        {"group": "A", "maximum": 4, "average": 6.0, "values": [2, 4]},
        {"group": "B", "maximum": 6, "average": 12.0, "values": [6, None]},
    ]


def test_conform_round_trip_executes_with_only_foreign_frame_and_explicit_keys(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    target = profile.Profile(
        id="target",
        grain=[group.resolution("group")],
        assembly=[
            assembly.Operator(
                id="read_target",
                inputs=[],
                outputs=[feature.Feature(id="base_value")],
                compute=assembly.Bind(
                    ref.function(read_conform_target),
                ),
                merge=merge.default(),
            ),
            assembly.Operator(
                id="conform_source",
                inputs=[ref.feature("source_value")],
                outputs=[feature.Feature(id="conformed_value")],
                compute=assembly.Bind(
                    ref.function(conform_source),
                    source=ref.profile("foreign").dataset,
                    matching_keys=ref.profile().grain.ids,
                ),
                merge=merge.default(),
            ),
        ],
    )
    foreign = profile.Profile(
        id="foreign",
        grain=[group.resolution("group")],
        assembly=[
            assembly.Operator(
                id="read_source",
                inputs=[],
                outputs=[feature.Feature(id="source_value")],
                compute=assembly.Bind(
                    ref.function(read_conform_source),
                ),
                merge=merge.default(),
            )
        ],
    )
    spec_definition = spec.from_python(profiles=[target, foreign])
    plan = compiler.Compiler().compile(spec_definition, features=["conformed_value"])
    portable = plan_module.from_dict(json.loads(json.dumps(plan_module.to_dict(plan))))
    conform_invocation = next(
        item for item in portable.invocations if item.semantics.operator_id == "conform_source"
    )
    source_merge = next(
        item
        for item in portable.invocations
        if item.semantics.operator_id == "read_source" and item.semantics.role == "merge"
    )
    assert all(item.semantics.operator_id != "read_target" for item in portable.invocations)

    assert conform_invocation.arguments == {
        "source": "foreign",
        "matching_keys": ["group"],
    }
    assert conform_invocation.semantics.dependency_ids == [source_merge.id]
    stage_by_id = {
        invocation_id: stage_number
        for stage_number, stage in enumerate(portable.stages)
        for invocation_id in stage
    }
    assert stage_by_id[source_merge.id] < stage_by_id[conform_invocation.id]

    result = engine_for_plan(portable, spec_definition=spec_definition).run()

    assert result.failures == {}
    assert set(result.invocation_statuses.values()) == {"succeeded"}
    assert result.datasets["target"].sort("group").to_dicts() == [
        {"group": "B", "conformed_value": 2},
        {"group": "C", "conformed_value": 3},
    ]


@pytest.mark.parametrize("foreign_seed", [False, True])
def test_profile_seed_is_persisted_and_runs_before_fragment_merges(
    foreign_seed: bool, engine_for_plan: execution_support.EngineFactory
) -> None:
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    if foreign_seed:
        seed = assembly.Operator(
            id="initial",
            inputs=[ref.feature("source_value")],
            outputs=[feature.Feature(id="conformed_value")],
            compute=assembly.Bind(
                ref.function(conform_source),
                source=ref.profile("foreign").dataset,
                matching_keys=ref.profile().grain.ids,
            ),
        )
        foreign = profile.Profile(
            id="foreign",
            grain=[group.resolution("group")],
            assembly=[
                assembly.Operator(
                    id="foreign_read",
                    outputs=[feature.Feature(id="source_value")],
                    compute=assembly.Bind(ref.function(read_conform_source)),
                    merge=merge.default(),
                )
            ],
        )
        profiles = [foreign]
    else:
        seed = assembly.Operator(
            id="initial",
            outputs=[feature.Feature(id="source_value")],
            compute=assembly.Bind(ref.function(read_conform_source)),
        )
        profiles = []

    target = profile.Profile(
        id="target",
        seed="initial",
        grain=[group.resolution("group")],
        assembly=[
            assembly.Operator(
                outputs=[feature.Feature(id="base_value")],
                compute=assembly.Bind(ref.function(read_conform_target)),
                merge=assembly.Bind(
                    ref.function(merge_seeded_dataset),
                    dataset=ref.dataset(),
                    fragment=ref.fragment(),
                ),
            ),
            seed,
        ],
    )
    spec_definition = spec.from_python(profiles=[target, *profiles])
    document = spec_serialization.to_document(spec_definition)
    restored = spec_model.Spec.model_validate(json.loads(json.dumps(document)))
    validate_spec(restored)
    assert restored.profiles["target"].seed == "initial"

    plan = compiler.Compiler().compile(restored, features=["base_value"])
    portable = plan_module.from_dict(json.loads(json.dumps(plan_module.to_dict(plan))))
    initial = next(item for item in portable.invocations if item.semantics.operator_id == "initial")
    merged = next(
        item
        for item in portable.invocations
        if item.semantics.profile_id == "target" and item.semantics.role == "merge"
    )
    assert initial.semantics.is_seed
    assert initial.id in merged.semantics.dependency_ids
    assert not any(
        item.semantics.operator_id == "initial" and item.semantics.role == "merge"
        for item in portable.invocations
    )

    result = engine_for_plan(portable, spec_definition=restored).run()
    assert result.failures == {}
    assert result.datasets["target"].sort("group")["group"].to_list() == ["A", "B", "C"]
    assert not any(profile_id == "target" for profile_id, _ in result.calculated_outputs)


def test_seed_requires_all_target_grain_keys(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    target = profile.Profile(
        id="target",
        grain=[group.resolution("group")],
        seed="initial",
        assembly=[
            assembly.Operator(
                id="initial",
                outputs=[feature.Feature(id="source_value")],
                compute=assembly.Bind(ref.function(read_reference_constant)),
            )
        ],
    )
    spec_definition = spec.from_python(profiles=[target])
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run()
    assert any("missing identifier columns: group" in error for error in result.failures.values())


def test_write_receives_the_seeded_dataset(
    tmp_path: pathlib.Path, engine_for_plan: execution_support.EngineFactory
) -> None:
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    output = tmp_path / "output.csv"
    target = profile.Profile(
        id="target",
        grain=[group.resolution("group")],
        seed="initial",
        assembly=[
            assembly.Operator(
                id="initial",
                outputs=[feature.Feature(id="source_value")],
                compute=assembly.Bind(ref.function(read_conform_source)),
            ),
            assembly.Operator(
                id="write",
                compute=assembly.Bind(
                    ref.function(write_seeded_dataset),
                    dataset=ref.dataset(),
                    output=str(output),
                ),
            ),
        ],
    )
    spec_definition = spec.from_python(profiles=[target])
    plan = compiler.Compiler().compile(spec_definition, features=["source_value"])
    seed = next(invocation for invocation in plan.invocations if invocation.semantics.is_seed)
    writer = next(
        invocation for invocation in plan.invocations if invocation.semantics.operator_id == "write"
    )
    assert seed.id in writer.semantics.dependency_ids

    result = engine_for_plan(plan, spec_definition=spec_definition).run()
    assert result.failures == {}
    assert pl.read_csv(output).to_dicts() == [
        {"group": "B", "source_value": 2},
        {"group": "C", "source_value": 3},
    ]


def test_dimensional_inputs_are_validated_against_the_foreign_dataframe() -> None:
    spec_definition = _spec()
    plan = compiler.Compiler().compile(spec_definition, features=["average"])
    invocation = next(item for item in plan.invocations if item.semantics.profile_id == "summary")
    invocation = copy.replace(
        invocation,
        semantics=copy.replace(invocation.semantics, input_features=["maximum"]),
    )
    state = state_module.RuntimeState(
        datasets={
            "summary": execution_support.dataset(pl.DataFrame({"group": ["A"], "maximum": [4]})),
            "observations": execution_support.dataset(
                pl.DataFrame({"group": ["A"], "id": [1], "value": [2], "doubled": [4]})
            ),
        }
    )
    executor = execution_module.InvocationExecutor(
        backend_module.create_backend(engine.EngineConfig().backend),
        {},
        {},
        state,
        validate=True,
    )

    with pytest.raises(ValueError, match="input feature.*foreign source profile: maximum"):
        executor.execute(invocation)
