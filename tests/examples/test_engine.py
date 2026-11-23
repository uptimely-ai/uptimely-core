import json
import pathlib
import sys
import tomllib

import polars as pl
import pump_analytics as analytics
import pump_io as io
import pytest
from support import examples as example_support
from support import execution as execution_support

from uptimely import application
from uptimely.cli import cli


def _engine_parameters() -> dict[str, object]:
    path = example_support.EXAMPLES_ROOT / "uptimely.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))["params"]


def _engine_paths(project_root: pathlib.Path) -> dict[str, str]:
    path = project_root / "uptimely.toml"
    configured_paths = tomllib.loads(path.read_text(encoding="utf-8"))["paths"]
    paths: dict[str, str] = {}
    for name, value in configured_paths.items():
        configured = pathlib.Path(value)
        paths[name] = str(configured if configured.is_absolute() else project_root / configured)
    return paths


def test_engine_returns_calculated_features_without_writing_output(
    pump_bundle: application.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        project_root=pump_bundle.project_root,
        spec_definition=pump_bundle.spec_definition,
        paths=_engine_paths(pump_bundle.project_root),
    )

    result = engine.run()

    assert not result.failures
    assert result.calculated_outputs is None
    pump_frame = result.datasets["pump"].collect()
    assert pump_frame.select("pump_id", "data_center_id", "server_room_id").sort("pump_id").select(
        "data_center_id", "server_room_id"
    ).rows() == [
        ("DC-01", "SR-A"),
        ("DC-01", "SR-A"),
        ("DC-01", "SR-B"),
        ("DC-02", "SR-C"),
        ("DC-02", "SR-C"),
        ("DC-02", "SR-D"),
    ]
    assert pump_frame.select(
        "pump_id",
        "pump_max_capacity",
        "series_max_capacity",
        "category_max_capacity",
        "max_capacity",
    ).sort("pump_id").rows() == [
        ("CWP-101", 125.0, 130.0, 100.0, 125.0),
        ("CWP-102", None, 130.0, 100.0, 130.0),
        ("CWP-201", None, None, 100.0, 100.0),
        ("CWP-301", 190.0, 200.0, 220.0, 190.0),
        ("CWP-302", None, None, 220.0, 220.0),
        ("CWP-401", None, 70.0, 80.0, 70.0),
    ]
    pump_frame = pump_frame.sort("pump_id")
    assert pump_frame["bearing_temperature_max"].to_list() == [68.7, 66.0, 64.5, 75.0, 72.0, 60.0]
    assert pump_frame["health_signal_normalized"].to_list() == pytest.approx(
        [0.16, -0.2, -0.4, 1.0, 0.6, -1.0]
    )
    telemetry_frame = result.datasets["pump_telemetry"].collect()
    assert "health_signal_normalized" not in telemetry_frame.columns
    assert {"data_center_id", "server_room_id"} <= set(telemetry_frame.columns)
    telemetry_frame = telemetry_frame.sort("pump_id", "timestamp")
    assert telemetry_frame.height == 10
    assert telemetry_frame.select("pump_id", "timestamp").n_unique() == 10
    assert telemetry_frame["pump_id"].unique().sort().to_list() == pump_frame["pump_id"].to_list()
    assert telemetry_frame["pump_mode"].to_list() == [
        "operational",
        "operational",
        "operational",
        "operational",
        "operational",
        "operational",
        "warning",
        "operational",
        "operational",
        "operational",
    ]
    telemetry_frame = telemetry_frame.filter(pl.col("pump_id").is_in(["CWP-101", "CWP-201"]))
    assert telemetry_frame["pump_id"].to_list() == ["CWP-101", "CWP-101", "CWP-201"]
    assert "operation_mode" not in telemetry_frame.columns
    assert telemetry_frame["mode"].to_list() == [
        "below_rated_flow",
        "at_or_above_rated_flow",
        "below_rated_flow",
    ]
    assert result.datasets["constants"].collect().to_dicts() == [
        {"gravity": 9.81, "room_temperature": 20.0}
    ]
    assert io.read_file(
        str(example_support.EXAMPLES_ROOT / "data/input/constants_dev.json")
    ).collect().to_dicts() == [{"gravity": 9.81, "room_temperature": 22.0}]
    efficiency = [5.3 * 118.0 / (36 * 17.9), 5.4 * 119.5 / (36 * 18.1), 4.1 * 83.0 / (36 * 11.7)]
    assert telemetry_frame["pressure_flow_efficiency"].to_list() == pytest.approx(efficiency)
    assert telemetry_frame["bearing_temperature_delta"].to_list() == [None, 0.5, None]
    assert telemetry_frame["bearing_temperature_rise"].to_list() == pytest.approx(
        [68.2 - 20.0, 68.7 - 20.0, 64.5 - 20.0]
    )
    assert telemetry_frame["vibration_delta"].to_list() == pytest.approx([None, 0.1, None])
    assert telemetry_frame["pump_health_score"].to_list() == pytest.approx(
        [None, efficiency[1] - 0.05 - 0.05, None]
    )
    intermediate = result.datasets["pump_telemetry_when_warning"].collect()
    assert intermediate.select("pump_id", "timestamp", "warning_vibration_rms").rows() == [
        ("CWP-301", telemetry_frame["timestamp"][1], 4.6)
    ]
    warning_profile = "pump_telemetry_by_hour_when_warning"
    warning_frame = result.datasets[warning_profile].collect()
    assert warning_frame.select("pump_id", "hour").rows() == [
        ("CWP-301", telemetry_frame["hour"][1])
    ]
    assert warning_frame["warning_hour_max_vibration_rms"].to_list() == [4.6]
    moved_features = {
        "recommended_flow_rate",
        "recommended_differential_pressure",
        "energy_cost_score",
        "converged",
        "operating_point_recommendation",
    }
    assert not moved_features.intersection(telemetry_frame.columns)
    assert warning_frame["recommended_flow_rate"].to_list() == [182.0]
    assert warning_frame["recommended_differential_pressure"].to_list() == [6.6]
    assert warning_frame["energy_cost_score"].to_list() == pytest.approx([30.0 / 182.0])
    assert warning_frame["converged"].to_list() == [False]
    assert warning_frame["operating_point_recommendation"].to_list() == [
        pytest.approx(
            {
                "recommended_flow_rate": 182.0,
                "recommended_differential_pressure": 6.6,
                "energy_cost_score": 30.0 / 182.0,
                "converged": False,
            }
        )
    ]

    assert result.datasets["pump_series"].collect().select(
        "machine_series_id", "bearing_temperature_series_max", "max_capacity_series"
    ).sort("machine_series_id").rows() == [
        ("SERIES-1", 68.7, 130.0),
        ("SERIES-2", 64.5, None),
        ("SERIES-3", 75.0, 200.0),
        ("SERIES-4", 72.0, None),
        ("SERIES-5", 60.0, 70.0),
    ]
    assert result.datasets["pump_category"].collect().select(
        "machine_category_id", "bearing_temperature_category_max", "max_capacity_category"
    ).sort("machine_category_id").rows() == [
        ("CHILLED-WATER", 68.7, 100.0),
        ("CONDENSER-WATER", 75.0, 220.0),
        ("DISTRIBUTION", 60.0, 80.0),
    ]
    assert result.datasets["pump_telemetry_by_minute"].collect().sort(
        "pump_id", "minute"
    ).rows() == [
        ("CWP-101", telemetry_frame["minute"][0], 68.2),
        ("CWP-101", telemetry_frame["minute"][1], 68.7),
        ("CWP-102", telemetry_frame["minute"][0], 65.5),
        ("CWP-102", telemetry_frame["minute"][1], 66.0),
        ("CWP-201", telemetry_frame["minute"][2], 64.5),
        ("CWP-301", telemetry_frame["minute"][0], 74.0),
        ("CWP-301", telemetry_frame["minute"][1], 75.0),
        ("CWP-302", telemetry_frame["minute"][0], 71.5),
        ("CWP-302", telemetry_frame["minute"][1], 72.0),
        ("CWP-401", telemetry_frame["minute"][0], 60.0),
    ]
    assert result.datasets["pump_telemetry_by_hour"].collect().sort("pump_id").rows() == [
        ("CWP-101", telemetry_frame["hour"][0], 68.7),
        ("CWP-102", telemetry_frame["hour"][0], 66.0),
        ("CWP-201", telemetry_frame["hour"][2], 64.5),
        ("CWP-301", telemetry_frame["hour"][0], 75.0),
        ("CWP-302", telemetry_frame["hour"][0], 72.0),
        ("CWP-401", telemetry_frame["hour"][0], 60.0),
    ]
    assert result.datasets["pump_telemetry_by_day"].collect().sort("pump_id").rows() == [
        ("CWP-101", telemetry_frame["day"][0], 68.7),
        ("CWP-102", telemetry_frame["day"][0], 66.0),
        ("CWP-201", telemetry_frame["day"][2], 64.5),
        ("CWP-301", telemetry_frame["day"][0], 75.0),
        ("CWP-302", telemetry_frame["day"][0], 72.0),
        ("CWP-401", telemetry_frame["day"][0], 60.0),
    ]


def test_warning_profile_handles_no_warning_records(
    tmp_path: pathlib.Path,
    pump_bundle: application.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    paths = _engine_paths(pump_bundle.project_root)
    source = tmp_path / "telemetry.json"
    pl.read_json(paths["telemetry_source"]).with_columns(
        pl.col("vibration_rms").clip(upper_bound=2.9)
    ).write_json(source)
    paths["telemetry_source"] = str(source)
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        project_root=pump_bundle.project_root,
        spec_definition=pump_bundle.spec_definition,
        paths=paths,
    )

    result = engine.run()

    assert not result.failures
    assert result.datasets["pump_telemetry"].collect().height == 10
    assert result.datasets["pump_telemetry_when_warning"].collect().is_empty()
    warning_frame = result.datasets["pump_telemetry_by_hour_when_warning"].collect()
    assert warning_frame.is_empty()
    assert warning_frame.schema["recommended_flow_rate"] == pl.Float64
    assert warning_frame.schema["converged"] == pl.Boolean
    assert warning_frame.schema["operating_point_recommendation"] == pl.Struct(
        {
            "recommended_flow_rate": pl.Float64,
            "recommended_differential_pressure": pl.Float64,
            "energy_cost_score": pl.Float64,
            "converged": pl.Boolean,
        }
    )


def test_hourly_warning_aggregates_only_warnings_by_pump_and_hour(
    tmp_path: pathlib.Path,
    pump_bundle: application.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    paths = _engine_paths(pump_bundle.project_root)
    readings = json.loads(pathlib.Path(paths["telemetry_source"]).read_text(encoding="utf-8"))
    first = next(
        row
        for row in readings
        if row["pump_id"] == "CWP-301" and row["timestamp"] == "2026-09-01T08:00:00Z"
    )
    first["bearing_temperature"] = 92.0
    normal = dict(
        first, timestamp="2026-09-01T08:02:00Z", bearing_temperature=70.0, flow_rate=999.0
    )
    later = dict(first, timestamp="2026-09-01T09:00:00Z", flow_rate=200.0)
    other = next(
        row
        for row in readings
        if row["pump_id"] == "CWP-302" and row["timestamp"] == "2026-09-01T08:00:00Z"
    )
    other["vibration_rms"] = 5.1
    other["flow_rate"] = None
    readings.extend([normal, later])
    source = tmp_path / "telemetry.json"
    source.write_text(json.dumps(readings), encoding="utf-8")
    paths["telemetry_source"] = str(source)
    output = tmp_path / "hourly-warning.json"
    paths["pump_telemetry_by_hour_when_warning_output"] = str(output)
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        project_root=pump_bundle.project_root,
        spec_definition=pump_bundle.spec_definition,
        paths=paths,
    )

    result = engine.run()

    assert not result.failures
    intermediate = result.datasets["pump_telemetry_when_warning"].collect()
    assert intermediate.height == 4
    hourly = (
        result.datasets["pump_telemetry_by_hour_when_warning"].collect().sort("pump_id", "hour")
    )
    assert hourly.height == 3
    rows = hourly.to_dicts()
    first_hour, second_hour, other_pump = rows
    assert first_hour["pump_id"] == "CWP-301"
    assert first_hour["hour"].hour == 8
    assert first_hour["warning_hour_mean_differential_pressure"] == pytest.approx((6.5 + 6.6) / 2)
    assert first_hour["warning_hour_mean_flow_rate"] == pytest.approx((175.0 + 182.0) / 2)
    assert first_hour["warning_hour_mean_motor_power"] == pytest.approx((29.0 + 30.0) / 2)
    assert first_hour["warning_hour_max_bearing_temperature"] == 92.0
    assert first_hour["warning_hour_max_vibration_rms"] == 4.6
    assert first_hour["recommended_flow_rate"] == pytest.approx(178.5)
    assert first_hour["recommended_differential_pressure"] == pytest.approx(6.55)
    assert first_hour["energy_cost_score"] == pytest.approx(29.5 / 178.5)
    assert first_hour["converged"] is False
    assert (second_hour["pump_id"], second_hour["hour"].hour) == ("CWP-301", 9)
    assert second_hour["recommended_flow_rate"] == 200.0
    assert (other_pump["pump_id"], other_pump["hour"].hour) == ("CWP-302", 8)
    assert other_pump["warning_hour_mean_flow_rate"] is None
    assert other_pump["recommended_flow_rate"] is None
    assert other_pump["energy_cost_score"] is None
    published = pl.read_json(output).sort("pump_id", "hour")
    assert published.select("pump_id", "recommended_flow_rate").rows() == [
        ("CWP-301", 178.5),
        ("CWP-301", 200.0),
        ("CWP-302", None),
    ]


def test_cooling_pump_telemetry_filters_by_server_room(example_projects: pathlib.Path) -> None:
    project_root = example_projects
    telemetry = io.read_pump_telemetry(
        str(project_root / "data/input/pump_telemetry.json"),
        str(project_root / "data/input/pump_assets.json"),
        server_room_id="SR-A",
    ).collect()

    assert telemetry["data_center_id"].unique().to_list() == ["DC-01"]
    assert telemetry["server_room_id"].unique().to_list() == ["SR-A"]
    assert telemetry["pump_id"].unique().sort().to_list() == ["CWP-101", "CWP-102"]


def test_engine_cli_reports_processed_profiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(tmp_path / "project")
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "run",
            "--project-root",
            str(project_root),
            "--log-level",
            "debug",
            "--preview",
            "1",
        ],
    )
    cli.main()

    output = capsys.readouterr().out
    assert "Scope:" not in output
    assert "Executing invocation " in output
    assert "Processed profile pump:" in output
    assert "Check fragment dataframe type" not in output
    assert "\x1b[" not in output


def test_engine_cli_reports_scoped_saved_build(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(
        tmp_path / "scoped-project", features=("health_signal_normalized",)
    )
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "run",
            "--project-root",
            str(project_root),
            "--log-level",
            "debug",
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Scope:" not in output
    assert "Processed profile pump: 8 features" in output


def test_engine_rejects_missing_path(
    pump_bundle: application.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    paths = _engine_paths(pump_bundle.project_root)
    paths.pop("telemetry_source")
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        project_root=pump_bundle.project_root,
        spec_definition=pump_bundle.spec_definition,
        paths=paths,
    )

    result = engine.run()

    assert any(
        "Unresolved path: telemetry_source" in message for message in result.failures.values()
    )


def test_engine_rejects_non_scalar_parameter_value(
    pump_bundle: application.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    with pytest.raises(ValueError, match="must be a scalar"):
        engine_for_plan(
            pump_bundle.execution_plan,
            {"dummy": {"value": "not_used"}},
            project_root=pump_bundle.project_root,
            spec_definition=pump_bundle.spec_definition,
            paths=_engine_paths(pump_bundle.project_root),
        )


def test_example_deltas_are_partitioned_and_ordered() -> None:
    frame = pl.DataFrame(
        {
            "pump": ["CWP-101", "CWP-201", "CWP-101", "CWP-201"],
            "timestamp": [2, 2, 1, 1],
            "bearing_temperature": [11.5, 22.5, 10.0, 20.0],
            "vibration_rms": [1.2, 2.4, 1.0, 2.0],
        }
    )

    result = analytics.delta(
        frame.lazy(),
        "bearing_temperature",
        ["pump"],
        "timestamp",
        1,
        "temperature_delta",
    )
    result = (
        analytics.delta(
            result,
            "vibration_rms",
            ["pump"],
            "timestamp",
            1,
            "vibration_delta",
        )
        .collect()
        .sort("pump", "timestamp")
    )

    assert result["pump"].to_list() == [
        "CWP-101",
        "CWP-101",
        "CWP-201",
        "CWP-201",
    ]
    assert result["temperature_delta"].null_count() == 2
    assert result["temperature_delta"].drop_nulls().to_list() == pytest.approx([1.5, 2.5])
    assert result["vibration_delta"].null_count() == 2
    assert result["vibration_delta"].drop_nulls().to_list() == pytest.approx([0.2, 0.4])


def test_engine_executes_requested_feature_and_its_dependencies(
    example_bundle_factory: example_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    bundle = example_bundle_factory(features=("health_signal_normalized",))
    engine = engine_for_plan(
        bundle.execution_plan,
        _engine_parameters(),
        project_root=bundle.project_root,
        spec_definition=bundle.spec_definition,
        paths=_engine_paths(bundle.project_root),
    )
    assert [
        feature
        for stage in engine.plan.execution_stages
        for invocation in stage
        if invocation.semantics.dataframe_input_scope == "target"
        for feature in invocation.semantics.output_features
    ] == [
        "max_capacity",
        "health_signal_normalized",
    ]
    assert all(
        "operator_kind" not in invocation.model_dump()
        for stage in engine.plan.execution_stages
        for invocation in stage
    )

    result = engine.run()

    assert result.datasets["pump"].collect().height == 6
