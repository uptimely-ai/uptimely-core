import math
from collections import abc

import polars as pl
import pytest
from examples.pump_analytics.functions import analytics


@pytest.mark.parametrize("dimensions", [[], ["plant", "pump"]])
def test_maximum_handles_grouping_and_null_readings(dimensions: list[str]) -> None:
    frame = pl.LazyFrame(
        {
            "plant": ["A", "A", "B", "B"],
            "pump": ["one", "one", "one", "one"],
            "temperature": [None, 10.0, -2.0, -5.0],
        }
    )

    result = analytics.maximum(frame, "temperature", dimensions, "maximum").collect()

    if dimensions:
        assert result.sort(dimensions).rows() == [("A", "one", 10.0), ("B", "one", -2.0)]
    else:
        assert result.rows() == [(10.0,)]
    assert result.columns == [*dimensions, "maximum"]


def test_maximum_preserves_all_null_groups() -> None:
    result = analytics.maximum(
        pl.LazyFrame({"pump": ["one", "one"], "temperature": [None, None]}),
        "temperature",
        ["pump"],
        "maximum",
    ).collect()

    assert result.rows() == [("one", None)]


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

    result = analytics.normalize_health_signal(
        frame, "signal", -2.0, 4.0, ["signal"], "normalized"
    ).collect()

    assert result["signal"].to_list() == values
    assert result["normalized"].to_list() == pytest.approx(expected)


def test_pressure_flow_efficiency_uses_hydraulic_power_units_and_propagates_nulls() -> None:
    frame = pl.LazyFrame(
        {
            "pressure": [6.0, 3.0, 0.0, None],
            "flow": [120.0, 60.0, 120.0, 120.0],
            "power": [20.0, 10.0, 20.0, 20.0],
        }
    )

    result = analytics.pressure_flow_efficiency(
        frame, ["pressure", "flow", "power"], "efficiency"
    ).collect()

    assert result["efficiency"].to_list() == pytest.approx([1.0, 0.5, 0.0, None])
    assert result.drop("efficiency").equals(frame.collect())


def test_pressure_flow_efficiency_retains_polars_zero_division_values() -> None:
    result = analytics.pressure_flow_efficiency(
        pl.LazyFrame({"pressure": [6.0, 0.0], "flow": [120.0, 120.0], "power": [0.0, 0.0]}),
        ["pressure", "flow", "power"],
        "efficiency",
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

    result = analytics.optimize_pump_operating_point(
        frame, ["pressure", "flow", "power", "temperature", "vibration"], "recommendation"
    )
    expected_fields = {
        "recommended_flow_rate": [120.0, 100.0, 80.0, 60.0, 40.0],
        "recommended_discharge_pressure": [6.0, 5.0, 4.0, 3.0, 2.0],
        "energy_cost_score": [0.2, 0.1, 0.1, 0.2, 0.1],
        "converged": [True, False, False, False, None],
    }
    struct = result.collect()["recommendation"]
    assert struct.struct.fields == list(expected_fields)
    for field, expected in expected_fields.items():
        extracted = analytics.extract_recommendation_value(
            result, field, "recommendation", "extracted"
        ).collect()
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
    result = analytics.optimize_pump_operating_point(
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
    ).collect()
    costs = result["recommendation"].struct.field("energy_cost_score").to_list()

    assert costs[0] == math.inf
    assert math.isnan(costs[1])
    assert costs[2] is None


def test_extract_recommendation_rejects_unknown_struct_field() -> None:
    frame = pl.LazyFrame({"recommendation": [{"known": 1.0}]})

    with pytest.raises(pl.exceptions.StructFieldNotFoundError, match="missing"):
        analytics.extract_recommendation_value(
            frame, "missing", "recommendation", "extracted"
        ).collect()


@pytest.mark.parametrize(
    "delta_function",
    [
        analytics.bearing_temperature_delta,
        analytics.vibration_delta_from_previous,
    ],
)
def test_deltas_use_all_partition_keys_and_preserve_null_gaps(
    delta_function: abc.Callable[[pl.LazyFrame, str, list[str], str, str], pl.LazyFrame],
) -> None:
    frame = pl.LazyFrame(
        {
            "plant": ["A", "B", "A", "A", "A", "B"],
            "pump": ["one"] * 6,
            "timestamp": [4, 2, 2, 1, 3, 1],
            "value": [7.0, 18.0, None, 10.0, 8.0, 20.0],
        }
    )

    result = delta_function(frame, "value", ["plant", "pump"], "timestamp", "delta").collect()

    assert result.drop("delta").equals(frame.collect())
    assert result["delta"].to_list() == [-1.0, -2.0, None, None, None, None]
