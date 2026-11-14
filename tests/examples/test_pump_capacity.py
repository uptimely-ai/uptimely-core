"""Capacity inheritance at pump, series, and category resolution."""

import json
import pathlib

import polars as pl
import pump_analytics as analytics
import pump_io as io
import pytest
from support import examples as example_support
from support import execution as execution_support

from uptimely import plan, project


def _configured_parameters(project_root: pathlib.Path) -> dict[str, object]:
    configuration = json.loads((project_root / "config/config.json").read_text(encoding="utf-8"))
    return configuration["params"]


def _configured_paths(project_root: pathlib.Path) -> dict[str, str]:
    configuration = json.loads((project_root / "config/config.json").read_text(encoding="utf-8"))
    paths: dict[str, str] = {}
    for name, value in configuration["paths"].items():
        configured = pathlib.Path(value)
        paths[name] = str(configured if configured.is_absolute() else project_root / configured)
    return paths


def test_capacity_uses_specificity_not_numeric_maximum() -> None:
    frame = pl.LazyFrame(
        {
            "pump_id": ["pump", "series", "category", "missing", "zero"],
            "pump_capacity": [80.0, None, None, None, 0.0],
            "series_capacity": [90.0, 90.0, None, None, 90.0],
            "category_capacity": [100.0, 100.0, 100.0, None, 100.0],
        }
    )

    result = analytics.first_non_null_value(
        frame,
        ["pump_capacity", "series_capacity", "category_capacity"],
        "max_capacity",
    ).collect()

    assert result["max_capacity"].to_list() == [80.0, 90.0, 100.0, None, 0.0]
    assert result.drop("max_capacity").equals(frame.collect())


def test_capacity_reader_preserves_nulls_with_float_type(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps([{"machine_series_id": "series", "max_capacity": None}]),
        encoding="utf-8",
    )

    result = io.read_file(
        str(path),
        rename={"max_capacity": "series_capacity"},
        schema={"max_capacity": "float"},
    ).collect()

    assert result.rows() == [("series", None)]
    assert result.schema["series_capacity"] == pl.Float64


def test_capacity_expansion_selects_only_capacity_and_identifiers() -> None:
    series = pl.LazyFrame(
        {
            "machine_series_id": ["s1", "s2"],
            "capacity": [90.0, None],
            "temperature": [60.0, 70.0],
        }
    )

    result = analytics.select_columns(
        series, ["machine_series_id", "capacity"], {"capacity": "series_capacity"}
    )

    assert result.collect().to_dicts() == [
        {"machine_series_id": "s1", "series_capacity": 90.0},
        {"machine_series_id": "s2", "series_capacity": None},
    ]


@pytest.mark.parametrize("validate", [False, True])
def test_selected_capacity_plan_joins_on_parent_identifiers(
    example_bundle_factory: example_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
    validate: bool,
) -> None:
    bundle = example_bundle_factory(features=("max_capacity",))
    restored = plan.from_dict(plan.to_dict(bundle.execution_plan))
    pump_profile = bundle.spec_definition.profiles["pump"]
    assert "machine_series_id" not in pump_profile.features
    assert "machine_category_id" not in pump_profile.features
    reader = next(
        invocation
        for invocation in restored.invocations
        if invocation.profile_id == "pump"
        and invocation.operator_id == "read_pump_capacity"
        and invocation.operator_kind == "read"
    )
    assert set(reader.fragment_keys) == {
        "pump_id",
        "machine_series_id",
        "machine_category_id",
        "server_room_id",
        "data_center_id",
    }
    assert reader.output_features == ["pump_max_capacity"]
    series_compute = next(
        invocation
        for invocation in restored.invocations
        if invocation.operator_id == "expand_series_capacity"
        and invocation.operator_kind == "expand"
    )
    assert series_compute.fragment_keys == reader.fragment_keys
    assert "pump_assets_source" not in series_compute.arguments
    reader_merge = next(
        invocation
        for invocation in restored.invocations
        if invocation.profile_id == "pump"
        and invocation.operator_id == "read_pump_capacity"
        and invocation.role == "merge"
    )
    series_merge = next(
        invocation
        for invocation in restored.invocations
        if invocation.operator_id == "expand_series_capacity" and invocation.role == "merge"
    )
    assert reader_merge.id not in series_merge.dependency_ids
    assert "key_columns" not in series_merge.arguments
    paths = _configured_paths(bundle.project_root)

    result = engine_for_plan(
        restored,
        parameters=_configured_parameters(bundle.project_root),
        project_root=bundle.project_root,
        spec_definition=bundle.spec_definition,
        paths=paths,
    ).run(validate=validate)

    assert not result.failures
    assert "rated_flow_rate" not in result.datasets["pump"].collect_schema().names()
    assert result.datasets["pump"].collect().sort("pump_id").select(
        "pump_id", "machine_series_id", "machine_category_id"
    ).rows() == [
        ("CWP-101", "SERIES-1", "CHILLED-WATER"),
        ("CWP-102", "SERIES-1", "CHILLED-WATER"),
        ("CWP-201", "SERIES-2", "CHILLED-WATER"),
        ("CWP-301", "SERIES-3", "CONDENSER-WATER"),
        ("CWP-302", "SERIES-4", "CONDENSER-WATER"),
        ("CWP-401", "SERIES-5", "DISTRIBUTION"),
    ]
    assert result.datasets["pump"].collect().sort("pump_id").select(
        "pump_id", "max_capacity"
    ).rows() == [
        ("CWP-101", 125.0),
        ("CWP-102", 130.0),
        ("CWP-201", 100.0),
        ("CWP-301", 190.0),
        ("CWP-302", 220.0),
        ("CWP-401", 70.0),
    ]


def test_automatic_capacity_merge_preserves_pumps_with_missing_series(
    tmp_path: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    bundle = example_bundle_factory(features=("max_capacity",))
    paths = _configured_paths(bundle.project_root)
    records = json.loads(pathlib.Path(paths["pump_series_source"]).read_text(encoding="utf-8"))
    records = [record for record in records if record["machine_series_id"] != "SERIES-1"]
    records.append({"machine_series_id": "unused", "max_capacity": 999.0})
    path = tmp_path / "series.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    paths["pump_series_source"] = str(path)

    result = engine_for_plan(
        bundle.execution_plan,
        parameters=_configured_parameters(bundle.project_root),
        project_root=bundle.project_root,
        spec_definition=bundle.spec_definition,
        paths=paths,
    ).run(validate=True)

    assert not result.failures
    pumps = result.datasets["pump"].collect()
    assert pumps.height == 6
    assert pumps.filter(pl.col("pump_id") == "CWP-102").select(
        "series_max_capacity", "max_capacity"
    ).rows() == [(None, 100.0)]


@pytest.mark.parametrize("validate", [False, True])
def test_selected_feature_runs_full_profile_writer_dependencies(
    tmp_path: pathlib.Path,
    example_bundle_factory: example_support.BundleFactory,
    engine_for_plan: execution_support.EngineFactory,
    validate: bool,
) -> None:
    bundle = example_bundle_factory(features=("max_capacity",))
    paths = _configured_paths(bundle.project_root)
    records = json.loads(pathlib.Path(paths["pump_assets_source"]).read_text(encoding="utf-8"))
    for record in records:
        record.pop("machine_series_id")
    path = tmp_path / "pumps.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    paths["pump_assets_source"] = str(path)

    result = engine_for_plan(
        bundle.execution_plan,
        parameters=_configured_parameters(bundle.project_root),
        project_root=bundle.project_root,
        spec_definition=bundle.spec_definition,
        paths=paths,
    ).run(validate=validate)

    assert len(result.failures) == 1
    failure_id = next(iter(result.failures))
    failed_invocation = next(
        invocation
        for invocation in bundle.execution_plan.invocations
        if invocation.id == failure_id
    )
    assert failed_invocation.operator_id == "read_pump_telemetry"


@pytest.mark.parametrize(
    ("pump_value", "series_value", "category_value", "expected"),
    [
        (80.0, 90.0, 100.0, 80.0),
        (None, 90.0, 100.0, 90.0),
        (None, None, 100.0, 100.0),
        (None, None, None, None),
        (0.0, 90.0, 100.0, 0.0),
    ],
)
def test_engine_resolves_capacity_with_validation(
    tmp_path: pathlib.Path,
    pump_bundle: project.BuildBundle,
    engine_for_plan: execution_support.EngineFactory,
    pump_value: float | None,
    series_value: float | None,
    category_value: float | None,
    expected: float | None,
) -> None:
    paths = _configured_paths(pump_bundle.project_root)
    for parameter, value in [
        ("pump_assets_source", pump_value),
        ("pump_series_source", series_value),
        ("pump_category_source", category_value),
    ]:
        records = json.loads(pathlib.Path(paths[parameter]).read_text(encoding="utf-8"))
        for record in records:
            record["max_capacity"] = value
        path = tmp_path / f"{parameter}.json"
        path.write_text(json.dumps(records), encoding="utf-8")
        paths[parameter] = str(path)

    result = engine_for_plan(
        pump_bundle.execution_plan,
        parameters=_configured_parameters(pump_bundle.project_root),
        project_root=pump_bundle.project_root,
        spec_definition=pump_bundle.spec_definition,
        paths=paths,
    ).run(validate=True)

    assert not result.failures
    pumps = result.datasets["pump"].collect().sort("pump_id")
    assert pumps["pump_id"].to_list() == [
        "CWP-101",
        "CWP-102",
        "CWP-201",
        "CWP-301",
        "CWP-302",
        "CWP-401",
    ]
    assert pumps["max_capacity"].to_list() == [expected] * 6
