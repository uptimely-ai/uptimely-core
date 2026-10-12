import json
from collections.abc import Sequence
from pathlib import Path

import polars as pl
import pytest

from uptimely.analytics import FeatureGraph
from uptimely.compile import Compiler
from uptimely.compile.execution_graph import CallableGraph
from uptimely.compile.render import _render_step
from uptimely.engine import Engine, PolarsBackend
from uptimely.plan import ExecutionPlan, Plan
from uptimely.spec import Specification
from uptimely.spec.python_spec import bind, dataset, dimension, entity, feature, mapping, ref


def read_values(lazy: bool = False, empty: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame(
        {"group": ["A", "A", "B", "B"], "id": [1, 2, 3, 4], "value": [2, 4, 6, None]}
    )
    if empty:
        frame = frame.clear()
    return frame.lazy() if lazy else frame


def read_null_groups(lazy: bool = False, empty: bool = False) -> pl.DataFrame | pl.LazyFrame:
    return read_values(lazy=lazy, empty=empty).with_columns(
        pl.when(pl.col("group") == "B").then(None).otherwise(pl.col("group")).alias("group")
    )


def double(column: str) -> pl.Expr:
    return pl.col(column) * 2


def maximum(column: str) -> pl.Expr:
    return pl.col(column).max().alias("ignored_name")


def average(column: str) -> pl.Expr:
    return pl.col(column).mean()


def total(column: str) -> pl.Expr:
    return pl.col(column).sum()


def values(column: str) -> pl.Expr:
    return pl.col(column).implode()


def summarize(column: str, calculated: str) -> dict[str, pl.Expr]:
    return {
        "maximum": maximum(column),
        "average": average(calculated),
        "values": values(column),
    }


def nested_maximum(inputs: dict[str, list[str]]) -> pl.Expr:
    return pl.sum_horizontal(inputs["columns"]).max()


def expanded_values(dataframe: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    return dataframe.select("group", "id", (pl.col("value") * 3).alias("expanded"))


def invalid_reducer(column: str) -> pl.Series:
    return pl.Series(column, [1])


def unaggregated(column: str) -> pl.Expr:
    return pl.col(column)


def _specification(*, lazy: bool = False, empty: bool = False) -> Specification:
    source = dataset.Dataset(
        id="observations",
        mappings=[
            mapping.Read(
                bind=bind.bind(read_values, lazy=lazy, empty=empty),
                features=[feature.Feature(id=name) for name in ("group", "id", "value")],
            ),
            mapping.Vectorize(
                bind=bind.bind(double, column=ref.feature("value")),
                features=[feature.Feature(id="doubled")],
            ),
            mapping.Vectorize(
                id="unneeded",
                bind=bind.bind(double, column=ref.feature("value")),
                features=[feature.Feature(id="unneeded")],
            ),
        ],
    )
    summary = dataset.Dataset(
        id="summary",
        mappings=[
            mapping.Collapse(
                id="group_summary",
                bind=bind.bind(
                    summarize, column=ref.feature("value"), calculated=ref.feature("doubled")
                ),
                features=[
                    feature.Feature(id=name) for name in ("group", "maximum", "average", "values")
                ],
            )
        ],
    )
    global_summary = dataset.Dataset(
        id="global",
        mappings=[
            mapping.Collapse(
                id="global_total",
                bind=bind.bind(total, column=ref.feature("maximum")),
                features=[feature.Feature(id="total")],
            ),
            mapping.Collapse(
                id="global_maximum",
                bind=bind.bind(maximum, column=ref.feature("maximum")),
                features=[feature.Feature(id="global_max")],
            ),
        ],
    )
    return Specification.from_python(
        entities=[
            entity.Entity(
                id="observation",
                name="Observation",
                dimensions=["group", "id"],
                datasets=[source],
            ),
            entity.Entity(id="group", name="Group", dimensions=["group"], datasets=[summary]),
            entity.Entity(id="global", name="Global", dimensions=[], datasets=[global_summary]),
        ],
        dimensions=[
            dimension.Dimension(id="group", type="string"),
            dimension.Dimension(id="id", type="integer"),
        ],
    )


class CountingBackend(PolarsBackend):
    def __init__(self) -> None:
        self.groups: list[tuple[list[str], int]] = []

    def collapse(self, frame: object, keys: Sequence[str], columns: Sequence[object]) -> object:
        self.groups.append((list(keys), len(columns)))
        return super().collapse(frame, keys, columns)


@pytest.mark.parametrize("lazy", [False, True])
def test_grouped_reducers_execute_together_with_calculated_inputs_and_aliases(lazy: bool) -> None:
    specification = _specification(lazy=lazy)
    graph = CallableGraph(specification)
    assert all(not hasattr(node, "source") for node in graph.callables)
    plan = Compiler(specification, features=["average"]).compile()
    assert not any("unneeded" in operation.output_features for operation in plan.operations)
    collapse = next(operation for operation in plan.operations if operation.kind == "collapse")
    mapping_model = specification.entities["group"].datasets[0].mappings["group_summary"]
    assert "source" not in mapping_model.model_dump()
    assert all("source" not in operation for operation in plan.to_dict()["operations"])
    display = _render_step(1, collapse, plan)
    assert "source" not in display
    assert "grouping_dimensions" not in display
    assert collapse.entrypoint == f"{__name__}:summarize"
    assert collapse.function_id == "summarize"
    assert not hasattr(collapse, "source")
    assert collapse.arguments == {"column": "value", "calculated": "doubled"}
    assert "group_by" not in collapse.__dict__
    assert len(collapse.dependency_ids) == 2
    assert "aggregate" not in plan.plan.resources["functions"]
    assert set(specification.functions.collapse) == {"summarize", "maximum", "total"}
    backend = CountingBackend()
    result = Engine(plan, backend=backend).execute()
    assert not result.failures
    assert backend.groups == [(["group"], 3)]
    frame = result.datasets["group", "summary"]
    assert isinstance(frame, pl.LazyFrame if lazy else pl.DataFrame)
    if lazy:
        frame = frame.collect()
    assert frame.sort("group").to_dicts() == [
        {"group": "A", "maximum": 4, "average": 6.0, "values": [2, 4]},
        {"group": "B", "maximum": 6, "average": 12.0, "values": [6, None]},
    ]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_chained_and_global_collapses_round_trip(lazy: bool, empty: bool, tmp_path: Path) -> None:
    specification = _specification(lazy=lazy, empty=empty)
    path = tmp_path / "spec.json"
    specification.to_json(path)
    restored_spec = Specification.from_json(path)
    plan = Compiler(restored_spec).compile()
    restored_plan = ExecutionPlan(Plan.from_dict(json.loads(json.dumps(plan.to_dict()))))
    result = Engine(restored_plan).execute()
    assert not result.failures
    frame = result.datasets["global", "global"]
    if lazy:
        frame = frame.collect()
    assert frame.to_dicts() == [{"total": 0 if empty else 10, "global_max": None if empty else 6}]
    assert "total" in FeatureGraph(restored_spec).feature_names


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_infers_assembled_dataset_from_nested_expanded_inputs(lazy: bool) -> None:
    source = dataset.Dataset(
        id="observations",
        mappings=[
            mapping.Read(
                bind=bind.bind(read_values, lazy=lazy),
                features=[feature.Feature(id=name) for name in ("group", "id", "value")],
            ),
            mapping.Expand(
                bind=bind.bind(expanded_values, dataframe=ref.dataset("observations")),
                features=[feature.Feature(id=name) for name in ("group", "id", "expanded")],
            ),
        ],
    )
    summary = dataset.Dataset(
        id="summary",
        mappings=[
            mapping.Collapse(
                bind=bind.bind(
                    nested_maximum,
                    inputs={"columns": [ref.feature("value"), ref.feature("expanded")]},
                ),
                features=[feature.Feature(id=name) for name in ("group", "combined_maximum")],
            )
        ],
    )
    specification = Specification.from_python(
        entities=[
            entity.Entity(
                id="observation", name="Observation", dimensions=["group", "id"], datasets=[source]
            ),
            entity.Entity(id="group", name="Group", dimensions=["group"], datasets=[summary]),
        ],
        dimensions=[
            dimension.Dimension(id="group", type="string"),
            dimension.Dimension(id="id", type="integer"),
        ],
    )
    plan = Compiler(specification, features=["combined_maximum"]).compile()
    collapse = next(operation for operation in plan.operations if operation.kind == "collapse")
    assert not hasattr(collapse, "source")
    assert {operation.kind for operation in plan.operations} == {"read", "expand", "collapse"}
    assert "source" not in summary.to_model().mappings["nested_maximum"].model_dump()
    result = Engine(plan).execute()
    assert not result.failures
    frame = result.datasets["group", "summary"]
    if lazy:
        frame = frame.collect()
    assert frame.sort("group").to_dicts() == [
        {"group": "A", "combined_maximum": 16},
        {"group": "B", "combined_maximum": 24},
    ]


def test_collapse_rejects_materialized_series_and_skips_dependents() -> None:
    specification = _specification()
    specification.functions.collapse["total"].entrypoint = f"{__name__}:invalid_reducer"
    result = Engine(Compiler(specification).compile()).execute()
    assert len(result.failures) == 1
    assert "must return an aggregation expression" in next(iter(result.failures.values()))
    assert all(
        status == "skipped"
        for operation_id, status in result.operation_statuses.items()
        if "global_maximum" in operation_id
    )


@pytest.mark.parametrize(
    ("shape", "message"),
    [
        ("missing", "missing outputs: average"),
        ("extra", "unexpected outputs: extra"),
        ("non_string", "non-string output identifiers"),
        ("expression", "must return a mapping"),
        ("non_expression", "must return an aggregation expression for average"),
    ],
)
def test_multi_output_collapse_rejects_invalid_returns(
    monkeypatch: pytest.MonkeyPatch, shape: str, message: str
) -> None:
    plan = Compiler(_specification(), features=["average"]).compile()
    result: dict[object, object] = dict(summarize("value", "doubled"))
    if shape == "missing":
        result.pop("average")
    elif shape == "extra":
        result["extra"] = maximum("value")
    elif shape == "non_string":
        result[1] = maximum("value")
    elif shape == "non_expression":
        result["average"] = 42

    def invalid_summary(column: str, calculated: str) -> object:
        return maximum(column) if shape == "expression" else result

    monkeypatch.setattr(f"{__name__}.summarize", invalid_summary)
    execution = Engine(plan).execute()
    assert len(execution.failures) == 1
    assert message in next(iter(execution.failures.values()))
    assert ("group", "summary") not in execution.datasets


def test_global_collapse_rejects_multiple_rows() -> None:
    specification = _specification()
    specification.functions.collapse["total"].entrypoint = f"{__name__}:unaggregated"
    result = Engine(Compiler(specification).compile()).execute()
    assert "dimensionless datasets allow at most one row" in next(iter(result.failures.values()))


@pytest.mark.parametrize("invalid", ["missing", "multiple"])
def test_collapse_rejects_unresolved_input_dataset(invalid: str) -> None:
    plan = Compiler(_specification(), features=["average"]).compile().to_dict()
    operation = next(item for item in plan["operations"] if item["kind"] == "collapse")
    if invalid == "missing":
        operation["dependency_ids"] = []
    else:
        producer = dict(next(item for item in plan["operations"] if item["kind"] == "read"))
        producer["id"] = "callable:read:read_values:observation:another_dataset:additional_read"
        producer["dataset_id"] = "another_dataset"
        plan["operations"].append(producer)
        plan["stages"][0].append(producer["id"])
        operation["dependency_ids"].append(producer["id"])
    result = Engine(ExecutionPlan(Plan.from_dict(plan))).execute()
    message = next(iter(result.failures.values()))
    assert "dependencies must identify one input dataset" in message


@pytest.mark.parametrize("lazy", [False, True])
def test_collapse_preserves_null_group_keys(lazy: bool) -> None:
    specification = _specification(lazy=lazy)
    specification.functions.read["read_values"].entrypoint = f"{__name__}:read_null_groups"
    result = Engine(Compiler(specification, features=["maximum"]).compile()).execute()
    assert not result.failures
    frame = result.datasets["group", "summary"]
    if lazy:
        frame = frame.collect()
    assert frame.sort("group").select("group", "maximum").rows() == [(None, 6), ("A", 4)]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_dimensionless_alignment_preserves_empty_fragments_and_user_column_names(
    lazy: bool, empty: bool
) -> None:
    left = pl.DataFrame({"__uptimely_global_key": [7]})
    right = pl.DataFrame({"right": [8]})
    if empty:
        right = right.clear()
    if lazy:
        left, right = left.lazy(), right.lazy()
    result = PolarsBackend().join(left, right, [])
    if lazy:
        result = result.collect()
    assert result.to_dicts() == [{"__uptimely_global_key": 7, "right": None if empty else 8}]
