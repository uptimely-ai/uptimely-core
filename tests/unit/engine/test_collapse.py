import dataclasses
import json
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler, engine, spec
from uptimely import execution_plan as plan_module
from uptimely.engine.dataframe import backend as backend_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.spec import functions
from uptimely.spec import model as spec_model
from uptimely.spec.python import actions, dimension, feature, profile, ref


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


def read_null_groups(lazy: bool = False, empty: bool = False) -> pl.DataFrame | pl.LazyFrame:
    return read_values(lazy, empty).with_columns(
        pl.when(pl.col("group") == "B").then(None).otherwise(pl.col("group")).alias("group")
    )


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


def expanded_values(
    dataset: pl.DataFrame | pl.LazyFrame,
    observation_ids_by_group: dict[str, list[int]],
) -> pl.DataFrame | pl.LazyFrame:
    keys: pl.DataFrame | pl.LazyFrame = pl.DataFrame(
        [
            (group, identifier)
            for group, identifiers in observation_ids_by_group.items()
            for identifier in identifiers
        ],
        schema={"group": pl.String, "id": pl.Int64},
        orient="row",
    )
    if isinstance(dataset, pl.LazyFrame):
        keys = keys.lazy()
    return dataset.join(keys, on="group").select(
        "group", "id", pl.col("expansion_value").alias("expanded")
    )


def read_expansion_input(lazy: bool) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"group": ["A", "B"], "expansion_value": [12, 18]})
    return frame.lazy() if lazy else frame


def read_reference_constant(lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"source_value": [10.0]})
    return frame.lazy() if lazy else frame


def read_group_limits(lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"group": ["A", "B"], "source_value": [5.0, 7.0]})
    return frame.lazy() if lazy else frame


def broadcast_reference(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    return source.select(pl.col(feature).alias(output))


def broadcast_group_limit(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    return source.select("group", pl.col(feature).alias(output))


def inflate_reference(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    fragment = source.select(pl.col(feature).alias(output))
    if isinstance(fragment, pl.LazyFrame):
        fragment = fragment.collect()
    return pl.concat([fragment, fragment])


def read_conform_target() -> pl.DataFrame:
    return pl.DataFrame({"group": ["A", "B"], "base_value": [10, 20]})


def read_conform_source() -> pl.DataFrame:
    return pl.DataFrame({"group": ["B", "C"], "source_value": [2, 3]})


def conform_source(source: pl.DataFrame, matching_keys: list[str]) -> pl.DataFrame:
    assert source.columns == ["group", "source_value"]
    assert matching_keys == ["group"]
    return source.select(*matching_keys, pl.col("source_value").alias("conformed_value"))


def nested_maximum(
    dataset: pl.DataFrame | pl.LazyFrame, columns: list[str]
) -> pl.DataFrame | pl.LazyFrame:
    return dataset.group_by("group").agg(pl.sum_horizontal(columns).max().alias("combined_maximum"))


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
        grain=[profile.Grain(group, "group"), profile.Grain(identifier, "id")],
        assembly=[
            actions.Action(
                id="read_values",
                inputs=[],
                function=ref.function(read_values, kind="read"),
                arguments={"lazy": lazy, "empty": empty},
                outputs=[feature.Feature(id=name) for name in ("group", "id", "value")],
            ),
            actions.Action(
                id="double",
                inputs=[ref.feature("value")],
                function=ref.function(double, kind="vectorize"),
                arguments={
                    "dataset": ref.current_profile().dataframe,
                    "column": ref.feature("value").id,
                    "output": ref.feature("doubled").id,
                },
                outputs=[feature.Feature(id="doubled")],
            ),
            actions.Action(
                id="unneeded",
                inputs=[ref.feature("value")],
                function=ref.function(double, kind="vectorize"),
                arguments={
                    "dataset": ref.current_profile().dataframe,
                    "column": ref.feature("value").id,
                    "output": ref.feature("unneeded").id,
                },
                outputs=[feature.Feature(id="unneeded")],
            ),
        ],
    )
    summary = profile.Profile(
        id="summary",
        grain=[profile.Grain(group, "group")],
        assembly=[
            actions.Action(
                id="group_summary",
                inputs=[ref.feature("value"), ref.feature("doubled")],
                function=ref.function(summarize, kind="collapse"),
                arguments={
                    "dataset": ref.profile("observations").dataframe,
                    "column": ref.feature("value").id,
                    "calculated": ref.feature("doubled").id,
                },
                outputs=[feature.Feature(id=name) for name in ("maximum", "average", "values")],
            )
        ],
    )
    global_summary = profile.Profile(
        id="global",
        assembly=[
            actions.Action(
                id="global_total",
                inputs=[ref.feature("maximum")],
                function=ref.function(total, kind="collapse"),
                arguments={"dataset": ref.profile("summary").dataframe},
                outputs=[feature.Feature(id="total")],
            ),
            actions.Action(
                id="global_maximum",
                inputs=[ref.feature("maximum")],
                function=ref.function(maximum, kind="collapse"),
                arguments={"dataset": ref.profile("summary").dataframe},
                outputs=[feature.Feature(id="global_max")],
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
    assert not any("unneeded" in item.output_features for item in plan.invocations)
    collapse = next(item for item in plan.invocations if item.function_kind == "collapse")
    assert collapse.input_features == ["value", "doubled"]
    assert len(collapse.dependency_ids) == 2
    result = engine_for_plan(plan, spec_definition=spec_definition).run()
    assert not result.failures
    frame = result.main_frames["summary"]
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
        grain=[profile.Grain(group, "group")],
        assembly=[
            actions.Action(
                id="read_target",
                inputs=[],
                function=ref.function(read_conform_target, kind="read"),
                arguments={},
                outputs=[feature.Feature(id="base_value")],
            ),
            actions.Action(
                id="conform_source",
                inputs=[ref.feature("source_value")],
                function=ref.function(conform_source, kind="conform"),
                arguments={
                    "source": ref.profile("foreign").dataframe,
                    "matching_keys": ref.current_profile().grain.ids,
                },
                outputs=[feature.Feature(id="conformed_value")],
            ),
        ],
    )
    foreign = profile.Profile(
        id="foreign",
        grain=[profile.Grain(group, "group")],
        assembly=[
            actions.Action(
                id="read_source",
                inputs=[],
                function=ref.function(read_conform_source, kind="read"),
                arguments={},
                outputs=[feature.Feature(id="source_value")],
            )
        ],
    )
    spec_definition = spec.from_python(profiles=[target, foreign])
    plan = compiler.Compiler().compile(spec_definition, features=["conformed_value"])
    portable = plan_module.from_dict(json.loads(json.dumps(plan_module.to_dict(plan))))
    conform_invocation = next(
        item for item in portable.invocations if item.function_kind == "conform"
    )
    source_read = next(item for item in portable.invocations if item.mapping_id == "read_source")
    target_read = next(item for item in portable.invocations if item.mapping_id == "read_target")

    assert conform_invocation.arguments == {
        "source": "foreign",
        "matching_keys": ["group"],
    }
    assert {source_read.id, target_read.id} <= set(conform_invocation.dependency_ids)
    stage_by_id = {
        invocation_id: stage_number
        for stage_number, stage in enumerate(portable.stages)
        for invocation_id in stage
    }
    assert stage_by_id[source_read.id] < stage_by_id[conform_invocation.id]
    assert stage_by_id[target_read.id] < stage_by_id[conform_invocation.id]

    result = engine_for_plan(portable, spec_definition=spec_definition).run()

    assert result.failures == {}
    assert set(result.invocation_statuses.values()) == {"succeeded"}
    assert result.main_frames["target"].sort("group").to_dicts() == [
        {"group": "A", "base_value": 10, "conformed_value": None},
        {"group": "B", "base_value": 20, "conformed_value": 2},
        {"group": "C", "base_value": None, "conformed_value": 3},
    ]


def test_dimensional_inputs_are_validated_against_the_foreign_dataframe() -> None:
    spec_definition = _spec()
    plan = compiler.Compiler().compile(spec_definition, features=["average"])
    invocation = next(item for item in plan.invocations if item.function_kind == "collapse")
    invocation = dataclasses.replace(invocation, input_features=["maximum"])
    state = state_module.RuntimeState(
        main_frames={
            "summary": execution_support.main_frame(pl.DataFrame({"group": ["A"], "maximum": [4]})),
            "observations": execution_support.main_frame(
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


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_chained_global_collapses_round_trip(
    lazy, empty, tmp_path: pathlib.Path, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _spec(lazy=lazy, empty=empty)
    path = tmp_path / "spec.json"
    spec.write_document(spec_definition, path)
    restored = spec.load_spec(path)
    plan = compiler.Compiler().compile(restored)
    portable = plan_module.from_dict(json.loads(json.dumps(plan_module.to_dict(plan))))
    result = engine_for_plan(portable, spec_definition=restored).run()
    assert not result.failures
    frame = result.main_frames["global"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.to_dicts() == [{"total": 0 if empty else 10, "global_max": None if empty else 6}]
    assert "total" in spec.FeatureGraph(restored).feature_names


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_consumes_expanded_features(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _spec(lazy=lazy)
    spec_definition.profiles.pop("global")
    source = spec_definition.profiles["observations"]
    source.features["expanded"] = spec.Feature(id="expanded")
    auxiliary = spec_model.Profile(
        id="expansion_input",
        features={"expansion_value": spec_model.Feature(id="expansion_value")},
        actions={
            "read_expansion": spec_model.Action(
                id="read_expansion",
                binding=spec_model.Binding(function="read_expansion_input", args={"lazy": lazy}),
                features={"outputs": ["$features.expansion_value"]},
            )
        },
    )
    auxiliary.grain = [spec_model.Grain(dimension="group", resolution="group")]
    spec_definition.profiles[auxiliary.id] = auxiliary
    spec_definition.functions.root["read_expansion_input"] = spec_model.FunctionTemplate(
        id="read_expansion_input",
        kind="read",
        returns="dataframe",
        entrypoint=f"{__name__}:read_expansion_input",
        args={"lazy": spec_model.Argument(id="lazy", type="boolean")},
    )
    source.actions["expanded"] = spec_model.Action(
        id="expanded",
        binding=spec_model.Binding(
            function="expanded_values",
            args={
                "dataset": "$profiles.expansion_input.dataframe",
                "observation_ids_by_group": {"A": [1, 2], "B": [3, 4]},
            },
        ),
        features={
            "inputs": ["$features.expansion_value"],
            "outputs": ["$features.expanded"],
        },
    )
    spec_definition.functions.root["expanded_values"] = spec_model.FunctionTemplate(
        id="expanded_values",
        kind="expand",
        returns="dataframe",
        entrypoint=f"{__name__}:expanded_values",
        args={
            "dataset": spec_model.Argument(id="dataset", type="dataframe"),
            "observation_ids_by_group": spec_model.Argument(
                id="observation_ids_by_group", type="object{str: array[integer]}"
            ),
        },
    )
    summary = spec_definition.profiles["summary"]
    summary.features = {"combined_maximum": spec.Feature(id="combined_maximum")}
    summary.actions = {
        "nested": spec_model.Action(
            id="nested",
            binding=spec_model.Binding(
                function="nested_maximum",
                args={
                    "dataset": "$profiles.observations.dataframe",
                    "columns": ["$features.value.id", "$features.expanded.id"],
                },
            ),
            features={
                "inputs": ["$features.value", "$features.expanded"],
                "outputs": ["$features.combined_maximum"],
            },
        )
    }
    spec_definition.functions.root["nested_maximum"] = spec_model.FunctionTemplate(
        id="nested_maximum",
        kind="collapse",
        returns="dataframe",
        entrypoint=f"{__name__}:nested_maximum",
        args={
            "dataset": spec_model.Argument(id="dataset", type="dataframe"),
            "columns": spec_model.Argument(id="columns", type="array[string]"),
        },
    )
    spec_definition = spec_model.Spec.model_validate(spec_definition.model_dump())
    result = engine_for_plan(
        compiler.Compiler().compile(spec_definition, features=["combined_maximum"]),
        spec_definition=spec_definition,
    ).run()
    assert not result.failures
    frame = result.main_frames["summary"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("group").to_dicts() == [
        {"group": "A", "combined_maximum": 16},
        {"group": "B", "combined_maximum": 24},
    ]


@pytest.mark.parametrize(
    ("shape", "message"),
    [
        ("missing", "missing output columns: average"),
        ("expression", "must return a Polars DataFrame or LazyFrame"),
        ("series", "must return a Polars DataFrame or LazyFrame"),
        ("dictionary", "must return a Polars DataFrame or LazyFrame"),
        ("duplicate", "duplicate dimension keys"),
    ],
)
def test_collapse_rejects_invalid_returns(
    monkeypatch, shape, message, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _spec()
    plan = compiler.Compiler().compile(spec_definition, features=["average"])
    original = summarize

    def invalid(dataset, column, calculated):
        if shape == "expression":
            return pl.col(column).max()
        if shape == "series":
            return pl.Series([1])
        if shape == "dictionary":
            return {"maximum": 1}
        frame = original(dataset, column, calculated)
        return frame.drop("average") if shape == "missing" else pl.concat([frame, frame])

    monkeypatch.setattr(f"{__name__}.summarize", invalid)
    result = engine_for_plan(plan, spec_definition=spec_definition).run(validate=True)
    assert message in next(iter(result.failures.values()))
    assert "summary" not in result.main_frames


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_preserves_null_group_keys(lazy, engine_for_plan: execution_support.EngineFactory):
    spec_definition = _spec(lazy=lazy)
    spec_definition.functions["read_values"].entrypoint = f"{__name__}:read_null_groups"
    result = engine_for_plan(
        compiler.Compiler().compile(spec_definition, features=["maximum"]),
        spec_definition=spec_definition,
    ).run()
    assert not result.failures
    frame = result.main_frames["summary"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("group").select("group", "maximum").rows() == [(None, 6), ("A", 4)]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("empty_left", "empty_right"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_dimensionless_alignment_preserves_empty_fragments_and_user_column_names(
    lazy, empty_left, empty_right
):
    left = pl.DataFrame({"__join_key": [7], "__join_key_": [9]})
    right = pl.DataFrame({"right": [8]})
    if empty_left:
        left = left.clear()
    if empty_right:
        right = right.clear()
    if lazy:
        left, right = left.lazy(), right.lazy()
    result = engine.PolarsBackend().join(left, right, [])
    if lazy:
        result = result.collect()
    expected = (
        []
        if empty_left and empty_right
        else [
            {
                "__join_key": None if empty_left else 7,
                "__join_key_": None if empty_left else 9,
                "right": None if empty_right else 8,
            }
        ]
    )
    assert result.to_dicts() == expected


@pytest.mark.parametrize("lazy", [False, True])
def test_dimensionless_alignment_rejects_multiple_global_rows(lazy):
    left = pl.DataFrame({"left": [1, 2]})
    right = pl.DataFrame({"right": [3]})
    if lazy:
        left, right = left.lazy(), right.lazy()

    main = execution_support.main_frame(left)
    with pytest.raises(ValueError, match="at most one row"):
        execution_support.merge_fragment(main, fragment_module.Fragment(right, ()))


def _broadcast_spec(
    reader: object, expand_function: object, source_dimension_ids: list[str], lazy: bool
) -> spec.Spec:
    """Build a two-profile spec expanding a lower-dimensional source feature."""
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    identifier = dimension.Dimension(
        id="id",
        resolutions=[dimension.Resolution(id="id", key="id", type="integer")],
    )
    dimensions = {"group": group, "id": identifier}
    observations = profile.Profile(
        id="observations",
        grain=[profile.Grain(group, "group"), profile.Grain(identifier, "id")],
        assembly=[
            actions.Action(
                id="read_values",
                inputs=[],
                function=ref.function(read_values, kind="read"),
                arguments={"lazy": lazy},
                outputs=[feature.Feature(id="value")],
            ),
            actions.Action(
                id="reference",
                inputs=[ref.feature("source_value")],
                function=ref.function(expand_function, kind="expand"),
                arguments={
                    "source": ref.profile("reference_source").dataframe,
                    "feature": ref.feature("source_value").id,
                    "output": ref.feature("reference").id,
                },
                outputs=[feature.Feature(id="reference")],
            ),
        ],
    )
    source = profile.Profile(
        id="reference_source",
        grain=[profile.Grain(dimensions[name], name) for name in source_dimension_ids],
        assembly=[
            actions.Action(
                id="read_reference",
                inputs=[],
                function=ref.function(reader, kind="read"),
                arguments={"lazy": lazy},
                outputs=[feature.Feature(id="source_value")],
            )
        ],
    )
    return spec.from_python(profiles=[observations, source])


@pytest.mark.parametrize("lazy", [False, True])
def test_expand_broadcasts_dimensionless_fragment(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _broadcast_spec(read_reference_constant, broadcast_reference, [], lazy)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run()

    assert not result.failures
    frame = result.main_frames["observations"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("id").to_dicts() == [
        {"group": "A", "id": 1, "value": 2, "reference": 10.0},
        {"group": "A", "id": 2, "value": 4, "reference": 10.0},
        {"group": "B", "id": 3, "value": 6, "reference": 10.0},
        {"group": "B", "id": 4, "value": None, "reference": 10.0},
    ]


@pytest.mark.parametrize("lazy", [False, True])
def test_expand_left_joins_fragment_on_its_carried_dimension_keys(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _broadcast_spec(read_group_limits, broadcast_group_limit, ["group"], lazy)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run()

    assert not result.failures
    frame = result.main_frames["observations"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("id").select("group", "id", "reference").rows() == [
        ("A", 1, 5.0),
        ("A", 2, 5.0),
        ("B", 3, 7.0),
        ("B", 4, 7.0),
    ]


def test_fragment_dimension_policy_is_independent_of_expand_id(
    monkeypatch: pytest.MonkeyPatch,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    spec_definition = _broadcast_spec(read_group_limits, broadcast_group_limit, ["group"], False)
    plan = compiler.Compiler().compile(spec_definition)
    definitions = dict(functions.FUNCTION_KINDS)
    definitions[functions.EXPAND] = dataclasses.replace(
        definitions[functions.EXPAND], fragment_dimensions="target"
    )
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    result = engine_for_plan(plan, spec_definition=spec_definition).run(validate=True)

    assert "missing dimension columns: id" in next(iter(result.failures.values()))


def test_expand_rejects_multirow_dimensionless_fragment(
    engine_for_plan: execution_support.EngineFactory,
):
    spec_definition = _broadcast_spec(read_reference_constant, inflate_reference, [], False)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run(validate=True)

    assert "at most one row" in next(iter(result.failures.values()))
