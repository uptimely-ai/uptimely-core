import json
import pathlib

import polars as pl
import pytest

from uptimely import compiler, engine, spec
from uptimely.compiler import plan as plan_module
from uptimely.spec import model as spec_model
from uptimely.spec.python import bind, dataset, dimension, entity, feature, mapping, ref


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
    dataset: pl.DataFrame | pl.LazyFrame, other_dataset: pl.DataFrame | pl.LazyFrame
) -> pl.DataFrame | pl.LazyFrame:
    return dataset.select("group", "id", (pl.col("value") * 3).alias("expanded"))


def read_expansion_input(lazy: bool) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"group": ["A", "B"], "expansion_value": [1, 1]})
    return frame.lazy() if lazy else frame


def nested_maximum(
    dataset: pl.DataFrame | pl.LazyFrame, columns: list[str]
) -> pl.DataFrame | pl.LazyFrame:
    return dataset.group_by("group").agg(pl.sum_horizontal(columns).max().alias("combined_maximum"))


def _spec(*, lazy=False, empty=False):
    source = dataset.Dataset(
        id="observations",
        mappings=[
            mapping.Mapping(
                bind=bind.bind(ref.function(read_values, operation="read"), lazy=lazy, empty=empty),
                outputs=[feature.Feature(id=name) for name in ("group", "id", "value")],
            ),
            mapping.Mapping(
                bind=bind.bind(
                    ref.function(double, operation="vectorize"),
                    dataset=ref.current_dataset().dataframe,
                    column=ref.feature("value").id,
                    output=ref.feature("doubled").id,
                ),
                inputs=[ref.feature("value")],
                outputs=[feature.Feature(id="doubled")],
            ),
            mapping.Mapping(
                id="unneeded",
                bind=bind.bind(
                    ref.function(double, operation="vectorize"),
                    dataset=ref.current_dataset().dataframe,
                    column=ref.feature("value").id,
                    output=ref.feature("unneeded").id,
                ),
                inputs=[ref.feature("value")],
                outputs=[feature.Feature(id="unneeded")],
            ),
        ],
    )
    summary = dataset.Dataset(
        id="summary",
        mappings=[
            mapping.Mapping(
                id="group_summary",
                bind=bind.bind(
                    ref.function(summarize, operation="collapse"),
                    dataset=ref.dataset("observations").dataframe,
                    column=ref.feature("value").id,
                    calculated=ref.feature("doubled").id,
                ),
                inputs=[ref.feature("value"), ref.feature("doubled")],
                outputs=[feature.Feature(id=name) for name in ("maximum", "average", "values")],
            ),
        ],
    )
    global_summary = dataset.Dataset(
        id="global",
        mappings=[
            mapping.Mapping(
                id="global_total",
                bind=bind.bind(
                    ref.function(total, operation="collapse"),
                    dataset=ref.dataset("summary").dataframe,
                ),
                inputs=[ref.feature("maximum")],
                outputs=[feature.Feature(id="total")],
            ),
            mapping.Mapping(
                id="global_maximum",
                bind=bind.bind(
                    ref.function(maximum, operation="collapse"),
                    dataset=ref.dataset("summary").dataframe,
                ),
                inputs=[ref.feature("maximum")],
                outputs=[feature.Feature(id="global_max")],
            ),
        ],
    )
    group = dimension.Dimension(id="group", type="string")
    identifier = dimension.Dimension(id="id", type="integer")
    return spec.from_python(
        entities=[
            entity.Entity(
                id="observation",
                name="Observation",
                dimensions=[group, identifier],
                datasets=[source],
            ),
            entity.Entity(id="group", name="Group", dimensions=[group], datasets=[summary]),
            entity.Entity(id="global", name="Global", dimensions=[], datasets=[global_summary]),
        ],
        dimensions=[group, identifier],
    )


@pytest.mark.parametrize("lazy", [False, True])
def test_grouped_dataframe_outputs_execute_once_with_calculated_inputs(lazy):
    spec_definition = _spec(lazy=lazy)
    plan = compiler.Compiler(spec_definition, features=["average"]).compile()
    assert not any("unneeded" in item.output_features for item in plan.callables)
    collapse = next(item for item in plan.callables if item.operation == "collapse")
    assert collapse.input_features == ["value", "doubled"]
    assert len(collapse.dependency_ids) == 2
    result = engine.Engine(plan).execute()
    assert not result.failures
    frame = result.datasets["group", "summary"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("group").to_dicts() == [
        {"group": "A", "maximum": 4, "average": 6.0, "values": [2, 4]},
        {"group": "B", "maximum": 6, "average": 12.0, "values": [6, None]},
    ]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_chained_global_collapses_round_trip(lazy, empty, tmp_path: pathlib.Path):
    spec_definition = _spec(lazy=lazy, empty=empty)
    path = tmp_path / "spec.json"
    spec.write_document(spec_definition, path)
    restored = spec.load_spec(path)
    plan = compiler.Compiler(restored).compile()
    portable = plan_module.ExecutionPlan(
        plan_module.Plan.from_dict(json.loads(json.dumps(plan.to_dict())))
    )
    result = engine.Engine(portable).execute()
    assert not result.failures
    frame = result.datasets["global", "global"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.to_dicts() == [{"total": 0 if empty else 10, "global_max": None if empty else 6}]
    assert "total" in spec.FeatureGraph(restored).feature_names


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_consumes_expanded_features(lazy):
    spec_definition = _spec(lazy=lazy)
    spec_definition.entities.pop("global")
    source = spec_definition.entities["observation"].datasets[0]
    source.features["expanded"] = spec.Feature(id="expanded")
    auxiliary = spec_model.Dataset(
        id="expansion_input",
        features={"expansion_value": spec_model.Feature(id="expansion_value")},
        mappings={
            "read_expansion": spec_model.Mapping(
                id="read_expansion",
                binding=spec_model.Binding(function="read_expansion_input", args={"lazy": lazy}),
                features={"outputs": ["$features.expansion_value"]},
            )
        },
    )
    spec_definition.entities["expansion"] = spec_model.Entity(
        id="expansion",
        name="Expansion",
        dimensions=[spec_definition.dimensions["group"]],
        datasets=[auxiliary],
    )
    spec_definition.functions.root["read_expansion_input"] = spec_model.FunctionTemplate(
        id="read_expansion_input",
        operation="read",
        returns="dataframe",
        entrypoint=f"{__name__}:read_expansion_input",
        args={"lazy": spec_model.Argument(id="lazy", type="boolean")},
    )
    source.mappings["expanded"] = spec_model.Mapping(
        id="expanded",
        binding=spec_model.Binding(
            function="expanded_values",
            args={
                "dataset": "$datasets.observations.dataframe",
                "other_dataset": "$datasets.expansion_input.dataframe",
            },
        ),
        features={
            "inputs": ["$features.value", "$features.expansion_value"],
            "outputs": ["$features.expanded"],
        },
    )
    spec_definition.functions.root["expanded_values"] = spec_model.FunctionTemplate(
        id="expanded_values",
        operation="expand",
        returns="dataframe",
        entrypoint=f"{__name__}:expanded_values",
        args={
            "dataset": spec_model.Argument(id="dataset", type="dataframe"),
            "other_dataset": spec_model.Argument(id="other_dataset", type="dataframe"),
        },
    )
    summary = spec_definition.entities["group"].datasets[0]
    summary.features = {"combined_maximum": spec.Feature(id="combined_maximum")}
    summary.mappings = {
        "nested": spec_model.Mapping(
            id="nested",
            binding=spec_model.Binding(
                function="nested_maximum",
                args={
                    "dataset": "$datasets.observations.dataframe",
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
        operation="collapse",
        returns="dataframe",
        entrypoint=f"{__name__}:nested_maximum",
        args={
            "dataset": spec_model.Argument(id="dataset", type="dataframe"),
            "columns": spec_model.Argument(id="columns", type="array[string]"),
        },
    )
    result = engine.Engine(
        compiler.Compiler(spec_definition, features=["combined_maximum"]).compile()
    ).execute()
    assert not result.failures
    frame = result.datasets["group", "summary"]
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
def test_collapse_rejects_invalid_returns(monkeypatch, shape, message):
    plan = compiler.Compiler(_spec(), features=["average"]).compile()
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
    result = engine.Engine(plan).execute()
    assert message in next(iter(result.failures.values()))
    assert ("group", "summary") not in result.datasets


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_preserves_null_group_keys(lazy):
    spec_definition = _spec(lazy=lazy)
    spec_definition.functions["read_values"].entrypoint = f"{__name__}:read_null_groups"
    result = engine.Engine(
        compiler.Compiler(spec_definition, features=["maximum"]).compile()
    ).execute()
    assert not result.failures
    frame = result.datasets["group", "summary"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("group").select("group", "maximum").rows() == [(None, 6), ("A", 4)]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_dimensionless_alignment_preserves_empty_fragments_and_user_column_names(lazy, empty):
    left = pl.DataFrame({"__uptimely_global_key": [7]})
    right = pl.DataFrame({"right": [8]})
    if empty:
        right = right.clear()
    if lazy:
        left, right = left.lazy(), right.lazy()
    result = engine.PolarsBackend().join(left, right, [])
    if lazy:
        result = result.collect()
    assert result.to_dicts() == [{"__uptimely_global_key": 7, "right": None if empty else 8}]
