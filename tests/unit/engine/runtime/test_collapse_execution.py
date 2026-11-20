import json
import pathlib

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler, engine, spec
from uptimely import plan as plan_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.spec import model as spec_model
from uptimely.spec.python import assembly, dimension, feature, merge, profile, ref


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
    frame = result.datasets["global"]
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
        assembly={
            "read_expansion": spec_model.Operator(
                id="read_expansion",
                compute=spec_model.Binding(function="read_expansion_input", args={"lazy": lazy}),
                interface=spec_model.Interface(outputs=["$features.expansion_value"]),
                merge=merge.default().to_model(),
            )
        },
    )
    auxiliary.grain = [spec_model.Grain(dimension="group", resolution="group")]
    spec_definition.profiles[auxiliary.id] = auxiliary
    spec_definition.functions.root["read_expansion_input"] = spec_model.FunctionTemplate(
        id="read_expansion_input",
        returns="dataframe",
        entrypoint=f"{__name__}:read_expansion_input",
        args={"lazy": spec_model.Argument(id="lazy", type="boolean")},
    )
    source.assembly["expanded"] = spec_model.Operator(
        id="expanded",
        compute=spec_model.Binding(
            function="expanded_values",
            args={
                "dataset": "$profiles.expansion_input.dataset",
                "observation_ids_by_group": {"A": [1, 2], "B": [3, 4]},
            },
        ),
        interface=spec_model.Interface(
            inputs=["$features.expansion_value"],
            outputs=["$features.expanded"],
        ),
        merge=merge.default().to_model(),
    )
    spec_definition.functions.root["expanded_values"] = spec_model.FunctionTemplate(
        id="expanded_values",
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
    summary.assembly = {
        "nested": spec_model.Operator(
            id="nested",
            compute=spec_model.Binding(
                function="nested_maximum",
                args={
                    "dataset": "$profiles.observations.dataset",
                    "columns": ["$features.value.id", "$features.expanded.id"],
                },
            ),
            interface=spec_model.Interface(
                inputs=["$features.value", "$features.expanded"],
                outputs=["$features.combined_maximum"],
            ),
            merge=merge.default().to_model(),
        )
    }
    spec_definition.functions.root["nested_maximum"] = spec_model.FunctionTemplate(
        id="nested_maximum",
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
    frame = result.datasets["summary"]
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
        ("duplicate", "duplicate identifiers"),
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
    assert "summary" not in result.datasets


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_preserves_null_group_keys(lazy, engine_for_plan: execution_support.EngineFactory):
    spec_definition = _spec(lazy=lazy)
    spec_definition.functions["read_values"].entrypoint = f"{__name__}:read_null_groups"
    result = engine_for_plan(
        compiler.Compiler().compile(spec_definition, features=["maximum"]),
        spec_definition=spec_definition,
    ).run()
    assert not result.failures
    frame = result.datasets["summary"]
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

    main = execution_support.dataset(left)
    with pytest.raises(ValueError, match="at most one row"):
        execution_support.merge_fragment(main, fragment_module.Fragment(right, ()))
