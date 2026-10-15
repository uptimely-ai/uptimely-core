import json
import pathlib

import pytest

from uptimely import analytics

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")


@pytest.mark.parametrize(
    "document",
    [
        {"version": "0.1.0"},
        {
            "version": "0.2.0",
            "functions": {"read": {"legacy_reader": {"entrypoint": "reader:load"}}},
        },
    ],
)
def test_legacy_function_catalog_schemas_are_rejected(
    tmp_path: pathlib.Path, document: dict[str, object]
) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        analytics.Analytics(json=path)


def test_mapping_validation(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "operation": "expand",
        "entrypoint": "examples.pump_analytics.functions.source:read_pump_telemetry",
        "args": {},
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["features"]["expanded_feature"] = {"type": "float", "description": "Expanded feature"}
    dataset["mappings"]["expand_op"] = {
        "binding": {"function": "expand_telemetry", "args": {}},
        "features": {"inputs": [], "outputs": ["$features.expanded_feature"]},
    }

    analytics_path = tmp_path / "valid_mappings_analytics.json"
    analytics_path.write_text(json.dumps(configuration), encoding="utf-8")
    parsed_analytics = analytics.Analytics(json=analytics_path)
    ds = parsed_analytics.entities["pump_telemetry"].datasets[0]

    assert "read_pump_telemetry" in ds.mappings
    assert "expand_op" in ds.mappings
    assert "expanded_feature" in ds.all_features

    bad_source_config = json.loads(json.dumps(configuration))
    bad_source_config["entities"]["pump_telemetry"]["datasets"][0]["features"][
        "bad_source_feature"
    ] = {"type": "float"}
    bad_source_config["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["bad_source"] = {
        "binding": {"function": "missing_read", "args": {}},
        "features": {"inputs": [], "outputs": ["$features.bad_source_feature"]},
    }
    bad_source_path = tmp_path / "bad_source.json"
    bad_source_path.write_text(json.dumps(bad_source_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        analytics.Analytics(json=bad_source_path)

    bad_transform_config = json.loads(json.dumps(configuration))
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["features"][
        "bad_transform_feature"
    ] = {"type": "float"}
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "bad_transform"
    ] = {
        "binding": {"function": "missing_expand", "args": {}},
        "features": {"inputs": [], "outputs": ["$features.bad_transform_feature"]},
    }
    bad_transform_path = tmp_path / "bad_transform.json"
    bad_transform_path.write_text(json.dumps(bad_transform_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        analytics.Analytics(json=bad_transform_path)


@pytest.mark.parametrize("mapping_id", ["bearing_temperature_by_pump", "health_signal_normalized"])
def test_mapping_rejects_explicit_source(tmp_path: pathlib.Path, mapping_id: str) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump"]["datasets"][0]["mappings"][mapping_id]["source"] = (
        "$datasets.pump_telemetry_dataset"
    )
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="source"):
        analytics.Analytics(json=invalid_operation_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("group_by", ["$dimensions.pump"], "group_by"),
        ("operations", {}, "operations"),
        (
            "features",
            {
                "inputs": ["$features.bearing_temperature"],
                "outputs": ["$features.plant", "$features.production_line", "$features.pump"],
            },
            "must produce a non-dimension feature",
        ),
        ("features", ["bearing_temperature_max"], "features"),
    ],
)
def test_collapse_validates_source_grouping_and_output_contract(
    tmp_path: pathlib.Path, field: str, value: object, message: str
) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        analytics.Analytics(json=path)


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ([], "must reference a source feature"),
        (["$features.health_signal_normalized"], "target dataset"),
        (["$features.bearing_temperature_max"], "target dataset"),
        (["$features.missing"], "unknown input feature"),
        (["$datasets.pump_telemetry_dataset"], "Mapping features must use"),
    ],
)
def test_collapse_validates_explicit_inputs(
    tmp_path: pathlib.Path, inputs: list, message: str
) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = inputs
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        analytics.Analytics(json=path)


@pytest.mark.parametrize("legacy", ["catalog", "source", "group_by", "operations", "aggregations"])
def test_removed_aggregation_and_wrapper_schemas_are_rejected(
    tmp_path: pathlib.Path, legacy: str
) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    if legacy == "catalog":
        configuration["functions"]["maximum"]["operation"] = "aggregate"
    else:
        collapse[legacy] = {}
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError):
        analytics.Analytics(json=path)


def test_collapse_inferred_dimensions_must_exist_in_source(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["dimensions"].remove("pump")
    path = tmp_path / "invalid_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="grouping dimensions must exist in source"):
        analytics.Analytics(json=path)


def test_collapse_catalog_requires_function_entrypoint(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["maximum"].pop("entrypoint")
    path = tmp_path / "missing_entrypoint.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="entrypoint"):
        analytics.Analytics(json=path)


def test_collapse_rejects_inputs_from_multiple_datasets(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    references = ["$features.bearing_temperature", "$features.health_signal_normalized"]
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = references
    path = tmp_path / "mixed_inputs.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="one dataset; use expand"):
        analytics.Analytics(json=path)


def test_collapse_dimensions_alone_do_not_identify_input_dataset(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = ["$features.pump"]
    path = tmp_path / "dimension_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="must reference a source feature"):
        analytics.Analytics(json=path)
