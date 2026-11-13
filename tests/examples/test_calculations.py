import math

import polars as pl
import pytest
from example.src import analytics


@pytest.mark.parametrize("value", ["warning", "absent"])
def test_filter_rows_selects_only_matches_and_preserves_empty_schema(value: str) -> None:
    frame = pl.LazyFrame(
        {
            "pump": ["one", "two", "three", "four"],
            "mode": ["operational", "warning", None, "warning"],
            "flow": [10.0, 20.0, 30.0, None],
        }
    )

    result = analytics.filter_rows(frame, "mode", value, {"flow": "warning_flow"}).collect()

    assert result.schema == {"pump": pl.String, "mode": pl.String, "warning_flow": pl.Float64}
    assert result.rows() == (
        [("two", "warning", 20.0), ("four", "warning", None)] if value == "warning" else []
    )
    assert frame.collect().height == 4


@pytest.mark.parametrize(
    ("temperature", "vibration", "expected"),
    [
        (89.9, 4.4, "operational"),
        (90.0, 4.4, "warning"),
        (89.9, 4.5, "warning"),
        (91.0, 5.0, "warning"),
        (None, 4.4, None),
        (89.9, None, None),
        (None, None, None),
        (None, 4.5, "warning"),
        (90.0, None, "warning"),
        (math.nan, 4.4, None),
        (89.9, math.nan, None),
        (math.inf, 4.4, None),
        (89.9, -math.inf, None),
        (math.nan, 4.5, "warning"),
        (90.0, math.inf, "warning"),
    ],
)
def test_pump_mode_handles_limits_and_invalid_readings(
    temperature: float | None, vibration: float | None, expected: str | None
) -> None:
    frame = pl.LazyFrame(
        {
            "pump": ["one"],
            "temperature": pl.Series([temperature], dtype=pl.Float64),
            "vibration": pl.Series([vibration], dtype=pl.Float64),
        }
    )

    result = analytics.pump_mode(frame, "temperature", "vibration", "mode", 90.0, 4.5).collect()

    assert result["mode"].dtype == pl.String
    assert result["mode"].to_list() == [expected]
    assert result.drop("mode").equals(frame.collect())


@pytest.mark.parametrize(
    ("temperature_limit", "vibration_limit", "expected_mode", "expected_converged"),
    [
        (70.0, 4.0, "warning", False),
        (80.0, 3.0, "warning", False),
        (80.0, 4.0, "operational", True),
    ],
)
def test_condition_calculations_use_supplied_limits(
    temperature_limit: float,
    vibration_limit: float,
    expected_mode: str,
    expected_converged: bool,
) -> None:
    frame = pl.LazyFrame(
        {"pressure": [4.0], "flow": [10.0], "power": [5.0], "temp": [70.0], "vib": [3.0]}
    )

    mode = analytics.pump_mode(
        frame, "temp", "vib", "mode", temperature_limit, vibration_limit
    ).collect()
    recommendation = analytics.operation_point_optimization(
        frame,
        ["pressure", "flow", "power", "temp", "vib"],
        "recommendation",
        temperature_limit,
        vibration_limit,
    ).collect()

    assert mode["mode"].to_list() == [expected_mode]
    assert recommendation["recommendation"].struct.field("converged").to_list() == [
        expected_converged
    ]


@pytest.mark.parametrize("rename", [{}, {"value": "reading", "other": "secondary"}])
def test_select_columns_preserves_order_rows_and_nulls(rename: dict[str, str]) -> None:
    frame = pl.LazyFrame(
        {"id": ["a", "a"], "value": [1.0, None], "other": [None, 2.0], "unused": [3, 4]}
    )

    result = analytics.select_columns(frame, ["other", "id", "value"], rename).collect()

    assert result.columns == [rename.get(column, column) for column in ["other", "id", "value"]]
    assert result.rows() == [(None, "a", 1.0), (2.0, "a", None)]


def test_select_columns_defaults_to_no_renaming() -> None:
    frame = pl.LazyFrame({"id": ["a"], "value": [1.0]})

    assert analytics.select_columns(frame, ["value"]).collect().to_dicts() == [{"value": 1.0}]


def test_select_columns_reports_missing_column() -> None:
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        analytics.select_columns(pl.LazyFrame({"id": ["a"]}), ["missing"]).collect()


@pytest.mark.parametrize("dimensions", [[], ["plant", "pump"]])
def test_aggregate_handles_grouping_and_null_readings(dimensions: list[str]) -> None:
    frame = pl.LazyFrame(
        {
            "plant": ["A", "A", "B", "B"],
            "pump": ["one", "one", "one", "one"],
            "temperature": [None, 10.0, -2.0, -5.0],
        }
    )

    result = analytics.aggregate(
        frame, {"temperature": "max"}, dimensions, {"temperature": "maximum"}
    ).collect()

    if dimensions:
        assert result.sort(dimensions).rows() == [("A", "one", 10.0), ("B", "one", -2.0)]
    else:
        assert result.rows() == [(10.0,)]
    assert result.columns == [*dimensions, "maximum"]


def test_aggregate_preserves_all_null_groups() -> None:
    result = analytics.aggregate(
        pl.LazyFrame({"pump": ["one", "one"], "temperature": [None, None]}),
        {"temperature": "max"},
        ["pump"],
        {"temperature": "maximum"},
    ).collect()

    assert result.rows() == [("one", None)]


def test_aggregate_rejects_unsupported_method() -> None:
    frame = pl.LazyFrame({"pump": ["one"], "temperature": [10.0]})

    with pytest.raises(ValueError, match="Unsupported aggregation method: median"):
        analytics.aggregate(frame, {"temperature": "median"}, ["pump"])


@pytest.mark.parametrize("dimensions", [[], ["pump"]])
def test_aggregate_multiple_methods_and_optional_renaming(dimensions: list[str]) -> None:
    frame = pl.LazyFrame(
        {
            "pump": ["one", "one", "two"],
            "flow": [2.0, 4.0, 8.0],
            "temperature": [None, 90.0, 85.0],
        }
    )

    result = analytics.aggregate(
        frame,
        {"flow": "mean", "temperature": "max"},
        dimensions,
        {"flow": "average_flow"},
    ).collect()

    assert result.columns == [*dimensions, "average_flow", "temperature"]
    if dimensions:
        assert result.sort("pump").rows() == [("one", 3.0, 90.0), ("two", 8.0, 85.0)]
    else:
        assert result.rows() == [(pytest.approx(14.0 / 3), 90.0)]


def test_aggregate_rejects_empty_aggregations_and_unknown_renames() -> None:
    frame = pl.LazyFrame({"temperature": [10.0]})

    with pytest.raises(ValueError, match="At least one aggregation is required"):
        analytics.aggregate(frame, {}, [])
    with pytest.raises(ValueError, match="Cannot rename non-aggregated columns: missing"):
        analytics.aggregate(frame, {"temperature": "max"}, [], {"missing": "other"})


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([10.0, 15.0, 20.0], [-2.0, 1.0, 4.0]),
        ([5.0, 5.0], [-2.0, -2.0]),
        ([5.0], [-2.0]),
        ([None, 10.0, 20.0], [None, -2.0, 4.0]),
        ([None, None], [None, None]),
        ([], []),
    ],
)
def test_normalization_handles_range_constant_null_and_empty_data(
    values: list[float | None], expected: list[float | None]
) -> None:
    frame = pl.LazyFrame({"signal": pl.Series(values, dtype=pl.Float64)})

    result = analytics.min_max_scale(frame, "signal", -2.0, 4.0, ["signal"], "normalized").collect()

    assert result["signal"].to_list() == values
    assert result["normalized"].to_list() == pytest.approx(expected)


def test_ratio_uses_hydraulic_power_units_and_propagates_nulls() -> None:
    frame = pl.LazyFrame(
        {
            "pressure": [6.0, 3.0, 0.0, None],
            "flow": [120.0, 60.0, 120.0, 120.0],
            "power": [20.0, 10.0, 20.0, 20.0],
        }
    )

    result = analytics.ratio(
        frame, ["pressure", "flow"], ["power"], "efficiency", scale=1.0 / 36.0
    ).collect()

    assert result["efficiency"].to_list() == pytest.approx([1.0, 0.5, 0.0, None])
    assert result.drop("efficiency").equals(frame.collect())


def test_ratio_retains_polars_zero_division_values() -> None:
    result = analytics.ratio(
        pl.LazyFrame({"pressure": [6.0, 0.0], "flow": [120.0, 120.0], "power": [0.0, 0.0]}),
        ["pressure", "flow"],
        ["power"],
        "efficiency",
        scale=1.0 / 36.0,
    ).collect()

    assert result["efficiency"][0] == math.inf
    assert math.isnan(result["efficiency"][1])


def test_health_score_penalizes_absolute_deltas_and_propagates_nulls() -> None:
    frame = pl.LazyFrame(
        {
            "temperature_delta": [2.0, -2.0, 0.0, None, 2.0, 2.0],
            "vibration_delta": [-0.4, 0.4, 0.0, 0.4, None, 0.4],
            "efficiency": [0.9, 0.9, 0.9, 0.9, 0.9, None],
        }
    )

    result = analytics.pump_health_score(
        frame, ["temperature_delta", "vibration_delta", "efficiency"], "health"
    ).collect()

    assert result["health"].to_list() == pytest.approx([0.5, 0.5, 0.9, None, None, None])


def test_optimization_struct_and_extraction_respect_convergence_boundaries() -> None:
    frame = pl.LazyFrame(
        {
            "pressure": [6.0, 5.0, 4.0, 3.0, 2.0],
            "flow": [120.0, 100.0, 80.0, 60.0, 40.0],
            "power": [24.0, 10.0, 8.0, 12.0, 4.0],
            "temperature": [89.9, 90.0, 89.9, 91.0, None],
            "vibration": [4.4, 4.4, 4.5, 5.0, 4.0],
        }
    )

    result = analytics.operation_point_optimization(
        frame,
        ["pressure", "flow", "power", "temperature", "vibration"],
        "recommendation",
        90.0,
        4.5,
    )
    expected_fields = {
        "recommended_flow_rate": [120.0, 100.0, 80.0, 60.0, 40.0],
        "recommended_differential_pressure": [6.0, 5.0, 4.0, 3.0, 2.0],
        "energy_cost_score": [0.2, 0.1, 0.1, 0.2, 0.1],
        "converged": [True, False, False, False, None],
    }
    struct = result.collect()["recommendation"]
    assert struct.struct.fields == list(expected_fields)
    for field, expected in expected_fields.items():
        extracted = analytics.extract_field(result, field, "recommendation", "extracted").collect()
        if field == "converged":
            assert struct.struct.field(field).dtype == pl.Boolean
            assert extracted["extracted"].dtype == pl.Boolean
            assert struct.struct.field(field).to_list() == expected
            assert extracted["extracted"].to_list() == expected
        else:
            assert struct.struct.field(field).to_list() == pytest.approx(expected)
            assert extracted["extracted"].to_list() == pytest.approx(expected)
        assert extracted.drop("recommendation", "extracted").equals(frame.collect())


def test_optimization_retains_zero_flow_and_null_power_costs() -> None:
    result = analytics.operation_point_optimization(
        pl.LazyFrame(
            {
                "pressure": [6.0, 6.0, 6.0],
                "flow": [0.0, 0.0, 120.0],
                "power": [20.0, 0.0, None],
                "temperature": [80.0, 80.0, 80.0],
                "vibration": [2.0, 2.0, 2.0],
            }
        ),
        ["pressure", "flow", "power", "temperature", "vibration"],
        "recommendation",
        90.0,
        4.5,
    ).collect()
    costs = result["recommendation"].struct.field("energy_cost_score").to_list()

    assert costs[0] == math.inf
    assert math.isnan(costs[1])
    assert costs[2] is None


def test_extract_field_rejects_unknown_struct_field() -> None:
    frame = pl.LazyFrame({"recommendation": [{"known": 1.0}]})

    with pytest.raises(pl.exceptions.StructFieldNotFoundError, match="missing"):
        analytics.extract_field(frame, "missing", "recommendation", "extracted").collect()


def test_delta_uses_all_partition_keys_and_preserves_null_gaps() -> None:
    frame = pl.LazyFrame(
        {
            "plant": ["A", "B", "A", "A", "A", "B"],
            "pump": ["one"] * 6,
            "timestamp": [4, 2, 2, 1, 3, 1],
            "value": [7.0, 18.0, None, 10.0, 8.0, 20.0],
        }
    )

    result = analytics.delta(frame, "value", ["plant", "pump"], "timestamp", 1, "delta").collect()

    assert result.drop("delta").equals(frame.collect())
    assert result["delta"].to_list() == [-1.0, -2.0, None, None, None, None]


def test_delta_uses_the_requested_number_of_rows() -> None:
    frame = pl.LazyFrame(
        {
            "pump": ["one"] * 4,
            "timestamp": [1, 2, 3, 4],
            "value": [10.0, 12.0, 16.0, 21.0],
        }
    )

    result = analytics.delta(frame, "value", ["pump"], "timestamp", 2, "delta").collect()

    assert result["delta"].to_list() == [None, None, 6.0, 9.0]
