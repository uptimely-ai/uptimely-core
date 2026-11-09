import json
import pathlib
import sys

import polars as pl
import pytest
from examples.pump_analytics.functions import analytics, source
from support import examples as example_support
from support import execution as execution_support

from uptimely import project
from uptimely.cli import cli
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import state as state_module


def _engine_parameters() -> dict[str, object]:
    path = example_support.EXAMPLES_ROOT / "pump_analytics/config/config.json"
    return json.loads(path.read_text(encoding="utf-8"))["params"]


def test_engine_returns_calculated_features_without_writing_output(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        _engine_parameters(),
        spec_definition=pump_bundle.spec_definition,
    )

    result = engine.run()

    assert not result.failures
    assert sorted({feature for _, feature in result.calculated_outputs}) == [
        "bearing_temperature_delta",
        "bearing_temperature_rise",
        "converged",
        "energy_cost_score",
        "health_signal_normalized",
        "max_capacity",
        "operating_point_recommendation",
        "pressure_flow_efficiency",
        "pump_health_score",
        "recommended_discharge_pressure",
        "recommended_flow_rate",
        "vibration_delta",
    ]
    assert isinstance(
        result.calculated_outputs[("pump", "health_signal_normalized")],
        pl.LazyFrame,
    )
    pump_frame = result.datasets["pump"].collect()
    assert pump_frame.select(
        "pump_id",
        "pump_max_capacity",
        "series_max_capacity",
        "category_max_capacity",
        "max_capacity",
    ).sort("pump_id").rows() == [
        ("PUMP-101", 125.0, 130.0, 100.0, 125.0),
        ("PUMP-102", None, 130.0, 100.0, 130.0),
        ("PUMP-201", None, None, 100.0, 100.0),
        ("PUMP-301", 190.0, 200.0, 220.0, 190.0),
        ("PUMP-302", None, None, 220.0, 220.0),
        ("PUMP-401", None, 70.0, 80.0, 70.0),
    ]
    pump_frame = pump_frame.sort("pump_id")
    assert pump_frame["bearing_temperature_max"].to_list() == [68.7, 66.0, 64.5, 75.0, 72.0, 60.0]
    assert pump_frame["health_signal_normalized"].to_list() == pytest.approx(
        [0.16, -0.2, -0.4, 1.0, 0.6, -1.0]
    )
    telemetry_frame = result.datasets["pump_telemetry"].collect()
    assert "health_signal_normalized" not in telemetry_frame.columns
    telemetry_frame = telemetry_frame.sort("pump_id", "timestamp")
    assert telemetry_frame.height == 10
    assert telemetry_frame.select("pump_id", "timestamp").n_unique() == 10
    assert telemetry_frame["pump_id"].unique().sort().to_list() == pump_frame["pump_id"].to_list()
    telemetry_frame = telemetry_frame.filter(pl.col("pump_id").is_in(["PUMP-101", "PUMP-201"]))
    assert telemetry_frame["pump_id"].to_list() == ["PUMP-101", "PUMP-101", "PUMP-201"]
    assert telemetry_frame["operation_mode"].to_list() == [
        "low_speed",
        "high_speed",
        "low_speed",
    ]
    assert result.datasets["constants"].collect().to_dicts() == [
        {"gravity": 9.81, "room_temperature": 20.0}
    ]
    assert source.read_file(
        str(example_support.EXAMPLES_ROOT / "pump_analytics/data/constants_dev.json")
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
    assert telemetry_frame["recommended_flow_rate"].to_list() == [118.0, 119.5, 83.0]
    assert telemetry_frame["recommended_discharge_pressure"].to_list() == [5.3, 5.4, 4.1]
    assert telemetry_frame["energy_cost_score"].to_list() == pytest.approx(
        [17.9 / 118.0, 18.1 / 119.5, 11.7 / 83.0]
    )
    assert telemetry_frame["converged"].to_list() == [True, True, True]
    recommendations = telemetry_frame["operating_point_recommendation"].to_list()
    for recommendation, flow, pressure, cost in zip(
        recommendations,
        [118.0, 119.5, 83.0],
        [5.3, 5.4, 4.1],
        [17.9 / 118.0, 18.1 / 119.5, 11.7 / 83.0],
        strict=True,
    ):
        assert recommendation == pytest.approx(
            {
                "recommended_flow_rate": flow,
                "recommended_discharge_pressure": pressure,
                "energy_cost_score": cost,
                "converged": True,
            }
        )
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
        ("CAT-1", 68.7, 100.0),
        ("CAT-2", 75.0, 220.0),
        ("CAT-3", 60.0, 80.0),
    ]
    assert result.datasets["pump_telemetry_by_minute"].collect().sort(
        "pump_id", "minute"
    ).rows() == [
        ("PUMP-101", telemetry_frame["minute"][0], 68.2),
        ("PUMP-101", telemetry_frame["minute"][1], 68.7),
        ("PUMP-102", telemetry_frame["minute"][0], 65.5),
        ("PUMP-102", telemetry_frame["minute"][1], 66.0),
        ("PUMP-201", telemetry_frame["minute"][2], 64.5),
        ("PUMP-301", telemetry_frame["minute"][0], 74.0),
        ("PUMP-301", telemetry_frame["minute"][1], 75.0),
        ("PUMP-302", telemetry_frame["minute"][0], 71.5),
        ("PUMP-302", telemetry_frame["minute"][1], 72.0),
        ("PUMP-401", telemetry_frame["minute"][0], 60.0),
    ]
    assert result.datasets["pump_telemetry_by_hour"].collect().sort("pump_id").rows() == [
        ("PUMP-101", telemetry_frame["hour"][0], 68.7),
        ("PUMP-102", telemetry_frame["hour"][0], 66.0),
        ("PUMP-201", telemetry_frame["hour"][2], 64.5),
        ("PUMP-301", telemetry_frame["hour"][0], 75.0),
        ("PUMP-302", telemetry_frame["hour"][0], 72.0),
        ("PUMP-401", telemetry_frame["hour"][0], 60.0),
    ]
    assert result.datasets["pump_telemetry_by_day"].collect().sort("pump_id").rows() == [
        ("PUMP-101", telemetry_frame["day"][0], 68.7),
        ("PUMP-102", telemetry_frame["day"][0], 66.0),
        ("PUMP-201", telemetry_frame["day"][2], 64.5),
        ("PUMP-301", telemetry_frame["day"][0], 75.0),
        ("PUMP-302", telemetry_frame["day"][0], 72.0),
        ("PUMP-401", telemetry_frame["day"][0], 60.0),
    ]


def test_engine_cli_reports_processed_profiles(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(tmp_path / "examples" / "pump_analytics")
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "engine",
            "run",
            "--project-root",
            str(project_root),
            "--log-level",
            "debug",
            "--validate",
            "--preview",
            "1",
        ],
    )
    cli.main()

    output = capsys.readouterr().out
    assert "Scope:" not in output
    assert "Processed profile pump: 10 features" in output
    assert "Profile: pump\n" in output
    assert "Profile: pump_telemetry\n" in output
    assert output.index("Processed profile pump: 10 features") < output.index("Profile: pump\n")
    assert "shape:" not in output
    assert "Executing operator read_constants, function read_file (read)" in output
    assert f"{'DEBUG':8} | Check fragment dataframe type" in output
    assert f"{'DEBUG':8} | Check dataset dataframe type" in output
    assert f"{'DEBUG':8} | Check values and row order of existing columns" in output
    assert "  Fragment:" not in output
    assert "  Requirements:" not in output
    assert "\n  Completed in " not in output
    assert "\x1b[" not in output


def test_engine_cli_reports_scoped_saved_build(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project_root = example_project_factory(
        tmp_path / "examples" / "pump_analytics", features=("health_signal_normalized",)
    )
    (project_root.parent / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "engine",
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
    assert "Processed profile pump: 10 features" in output


def test_engine_rejects_missing_parameter(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    parameters = _engine_parameters()
    parameters.pop("telemetry_source")
    engine = engine_for_plan(
        pump_bundle.execution_plan, parameters, spec_definition=pump_bundle.spec_definition
    )

    result = engine.run()

    assert any(
        "Unresolved parameter: telemetry_source" in message for message in result.failures.values()
    )


def test_engine_rejects_unknown_parameter_name(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    parameters = _engine_parameters()
    parameters.pop("telemetry_source")
    parameters["another_parameter"] = "value"
    engine = engine_for_plan(
        pump_bundle.execution_plan,
        parameters,
        spec_definition=pump_bundle.spec_definition,
    )

    result = engine.run()

    assert any(
        "Unresolved parameter: telemetry_source" in message for message in result.failures.values()
    )


def test_engine_rejects_non_scalar_parameter_value(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    with pytest.raises(ValueError, match="must be a JSON scalar"):
        engine_for_plan(
            pump_bundle.execution_plan,
            {"telemetry_source": {"path": "input.json"}},
            spec_definition=pump_bundle.spec_definition,
        )


def test_engine_merges_fragments_by_profile_grain_keys(
    pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    existing = pl.LazyFrame(
        {
            "pump_id": ["PUMP-101", "PUMP-201"],
            "existing": [1, 2],
        }
    )
    fragment = pl.LazyFrame(
        {
            "pump_id": ["PUMP-201", "PUMP-101"],
            "new": [20, 10],
        }
    )

    operation = next(
        operation for operation in engine.plan.invocations if operation.profile_id == "pump"
    )
    grain_keys = engine.spec_definition.grain_keys_by_profile[operation.profile_id]
    main = execution_support.dataset(
        existing,
        grain_keys,
        backend=engine.backend,
    )
    execution_support.merge_fragment(
        main,
        fragment_module.Fragment(fragment, tuple(grain_keys)),
    )
    merged = main.dataframe.collect()

    assert merged.select("pump_id", "existing", "new").sort("pump_id").rows() == [
        ("PUMP-101", 1, 10),
        ("PUMP-201", 2, 20),
    ]


@pytest.mark.parametrize(("existing_lazy", "fragment_lazy"), [(True, False), (False, True)])
def test_engine_assembly_accepts_mixed_eager_and_lazy_frames(
    existing_lazy: bool,
    fragment_lazy: bool,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    existing: pl.DataFrame | pl.LazyFrame = pl.DataFrame({"key": ["A"], "old": [1]})
    fragment: pl.DataFrame | pl.LazyFrame = pl.DataFrame({"key": ["B"], "new": [2]})
    if existing_lazy:
        existing = existing.lazy()
    if fragment_lazy:
        fragment = fragment.lazy()

    main = execution_support.dataset(
        existing,
        ["key"],
        backend=engine.backend,
    )
    main.merge(fragment_module.Fragment(fragment, ("key",)))
    merged = main.dataframe

    assert isinstance(merged, pl.LazyFrame)
    assert merged.collect().sort("key").select("key", "old", "new").rows() == [
        ("A", 1, None),
        ("B", None, 2),
    ]


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("existing_keys", "fragment_keys", "expected_keys"),
    [
        ([None, "A"], [None, "B"], [None, "A", "B"]),
        (["A"], ["B"], ["A", "B"]),
    ],
)
def test_engine_assembly_preserves_partial_and_disjoint_keys(
    lazy: bool,
    existing_keys: list[str | None],
    fragment_keys: list[str | None],
    expected_keys: list[str | None],
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    existing = pl.DataFrame({"key": existing_keys, "old": list(range(len(existing_keys)))})
    fragment = pl.DataFrame({"key": fragment_keys, "new": list(range(10, 10 + len(fragment_keys)))})
    if lazy:
        existing, fragment = existing.lazy(), fragment.lazy()

    main = execution_support.dataset(
        existing,
        ["key"],
        backend=engine.backend,
    )
    main.merge(fragment_module.Fragment(fragment, ("key",)))
    merged = main.dataframe
    if isinstance(merged, pl.LazyFrame):
        merged = merged.collect()

    assert sorted(merged["key"].to_list(), key=lambda value: value or "") == sorted(
        expected_keys, key=lambda value: value or ""
    )
    if None in existing_keys:
        assert merged.filter(pl.col("key").is_null()).select("old", "new").row(0) == (0, 10)


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("duplicate_side", ["existing", "fragment"])
def test_engine_assembly_rejects_duplicate_keys_on_either_side(
    lazy: bool,
    duplicate_side: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    existing = pl.DataFrame({"key": ["A", "A"], "old": [1, 2]})
    fragment = pl.DataFrame({"key": ["A"], "new": [3]})
    if duplicate_side == "fragment":
        existing = pl.DataFrame({"key": ["A"], "old": [1]})
        fragment = pl.DataFrame({"key": ["A", "A"], "new": [3, 4]})
    if lazy:
        existing, fragment = existing.lazy(), fragment.lazy()

    main = execution_support.dataset(
        existing,
        ["key"],
        backend=engine.backend,
    )
    with pytest.raises(ValueError, match="duplicate dimension keys"):
        execution_support.merge_fragment(main, fragment_module.Fragment(fragment, ("key",)))


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize("invalid_column", ["key", "output", "missing"])
def test_engine_validates_required_fragment_columns_and_types(
    lazy: bool,
    invalid_column: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.profile_id == "pump" and item.function_kind == "collapse"
    )
    grain_keys = engine.spec_definition.grain_keys_by_profile[invocation.profile_id]
    output = next(name for name in invocation.output_features if name not in grain_keys)
    columns: dict[str, list[object]] = {name: [f"{name}-1"] for name in grain_keys}
    columns[output] = ["wrong type" if invalid_column == "output" else 1.5]
    if invalid_column == "key":
        columns[grain_keys[0]] = [1]
    if invalid_column == "missing":
        columns.pop(output)
    result: pl.DataFrame | pl.LazyFrame = pl.DataFrame(columns)
    if lazy:
        result = result.lazy()

    expected = {
        "key": f"Output column {grain_keys[0]} has type",
        "output": f"Output column {output} has type",
        "missing": f"missing output columns: {output}",
    }[invalid_column]
    main = execution_support.dataset(
        None,
        grain_keys,
        backend=engine.backend,
    )
    with pytest.raises(ValueError, match=expected):
        execution_support.merge_fragment(
            main,
            fragment_module.Fragment(result, main.id_columns, invocation),
        )


@pytest.mark.parametrize("lazy", [False, True])
def test_engine_assembly_rejects_feature_collisions(
    lazy: bool, pump_bundle: project.BuildBundle, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    invocation = next(
        item
        for item in engine.plan.invocations
        if item.profile_id == "pump" and item.function_kind == "collapse"
    )
    grain_keys = engine.spec_definition.grain_keys_by_profile[invocation.profile_id]
    output = next(name for name in invocation.output_features if name not in grain_keys)
    keys = {name: [f"{name}-1"] for name in grain_keys}
    result = pl.DataFrame({**keys, output: [1.5]})
    existing = pl.DataFrame({**keys, output: [2.5]})
    if lazy:
        result, existing = result.lazy(), existing.lazy()

    main = execution_support.dataset(
        existing,
        grain_keys,
        backend=engine.backend,
    )
    with pytest.raises(ValueError, match=f"overlap.*{output}"):
        execution_support.merge_fragment(
            main,
            fragment_module.Fragment(result, main.id_columns, invocation),
        )


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        (None, "must return a Polars DataFrame or LazyFrame"),
        (pl.LazyFrame({"plant": ["PLANT-01"]}), "missing dimension columns"),
        (
            pl.LazyFrame({"pump_id": ["PUMP-101", "PUMP-101"]}),
            "duplicate dimension keys",
        ),
    ],
)
def test_engine_rejects_invalid_fragments(
    fragment: object,
    message: str,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    engine = engine_for_plan(
        pump_bundle.execution_plan, spec_definition=pump_bundle.spec_definition
    )
    operation = next(
        operation for operation in engine.plan.invocations if operation.profile_id == "pump"
    )

    main = execution_support.dataset(
        None,
        engine.spec_definition.grain_keys_by_profile[operation.profile_id],
        backend=engine.backend,
    )
    with pytest.raises(ValueError, match=message):
        execution_support.merge_fragment(
            main,
            fragment_module.Fragment(fragment, main.id_columns, operation),
        )


def test_engine_looks_up_profiles_by_project_wide_id() -> None:
    frame = pl.LazyFrame({"id": [1]})
    state = state_module.RuntimeState(datasets={"shared": execution_support.dataset(frame)})

    assert state.resolve_dataset_or_fragment_dataframe("shared") is frame
    assert state.resolve_dataset_or_fragment_dataframe("missing") is None


def test_example_deltas_are_partitioned_and_ordered() -> None:
    frame = pl.DataFrame(
        {
            "pump": ["PUMP-101", "PUMP-201", "PUMP-101", "PUMP-201"],
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
        "PUMP-101",
        "PUMP-101",
        "PUMP-201",
        "PUMP-201",
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
        bundle.execution_plan, _engine_parameters(), spec_definition=bundle.spec_definition
    )
    assert [
        feature
        for stage in engine.plan.execution_stages
        for operation in stage
        if operation.function_kind == "vectorize"
        for feature in operation.output_features
    ] == [
        "health_signal_normalized",
    ]
    assert {
        operation.function_kind for stage in engine.plan.execution_stages for operation in stage
    } == {
        "read",
        "merge",
        "collapse",
        "vectorize",
    }

    result = engine.run()

    assert result.datasets["pump"].collect().height == 6
