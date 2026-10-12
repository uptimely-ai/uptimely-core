import json
from pathlib import Path

import pytest

from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/_generated/spec/spec.json")


def test_mapping_validation(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand"] = {
        "expand_telemetry": {
            "entrypoint": "examples.example_1.functions.source:read_pump_telemetry",
            "args": {},
        }
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["features"]["expanded_feature"] = {"type": "float", "description": "Expanded feature"}
    dataset["mappings"]["expand_op"] = {
        "binding": {"function": "expand_telemetry", "args": {}},
        "features": [
            "plant",
            "production_line",
            "pump",
            "timestamp",
            "expanded_feature",
        ],
    }

    spec_path = tmp_path / "valid_mappings_spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")
    parsed_spec = Specification.from_json(spec_path)
    ds = parsed_spec.entities["pump_telemetry"].datasets[0]

    assert "read_pump_telemetry" in ds.mappings
    assert "expand_op" in ds.mappings
    assert "expanded_feature" in ds.all_features

    bad_source_config = json.loads(json.dumps(configuration))
    bad_source_config["entities"]["pump_telemetry"]["datasets"][0]["features"][
        "bad_source_feature"
    ] = {"type": "float"}
    bad_source_config["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["bad_source"] = {
        "binding": {"function": "missing_read", "args": {}},
        "features": ["bad_source_feature"],
    }
    bad_source_path = tmp_path / "bad_source.json"
    bad_source_path.write_text(json.dumps(bad_source_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        Specification.from_json(bad_source_path)

    bad_transform_config = json.loads(json.dumps(configuration))
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["features"][
        "bad_transform_feature"
    ] = {"type": "float"}
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "bad_transform"
    ] = {
        "binding": {"function": "missing_expand", "args": {}},
        "features": ["bad_transform_feature"],
    }
    bad_transform_path = tmp_path / "bad_transform.json"
    bad_transform_path.write_text(json.dumps(bad_transform_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        Specification.from_json(bad_transform_path)


@pytest.mark.parametrize("mapping_id", ["bearing_temperature_by_pump", "health_signal_normalized"])
def test_mapping_rejects_explicit_source(tmp_path: Path, mapping_id: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump"]["datasets"][0]["mappings"][mapping_id]["source"] = (
        "$datasets.pump_telemetry_dataset"
    )
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="source"):
        Specification.from_json(invalid_operation_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("group_by", ["$dimensions.pump"], "group_by"),
        ("operations", {}, "operations"),
        ("features", ["plant", "production_line", "pump"], "must produce a non-dimension feature"),
        ("features", ["bearing_temperature_max"], "must include dimension columns"),
    ],
)
def test_collapse_validates_source_grouping_and_output_contract(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        Specification.from_json(path)


@pytest.mark.parametrize(
    ("function", "args", "message"),
    [
        ("missing", {"feature": "$features.bearing_temperature"}, "unknown functions"),
        ("maximum", {}, "must reference a source feature"),
        ("maximum", {"feature": "$features.health_signal_normalized"}, "target dataset"),
        ("maximum", {"feature": "$features.bearing_temperature_max"}, "target dataset"),
        ("maximum", {"feature": "$features.missing"}, "unknown input feature"),
        (
            "maximum",
            {"feature": "$features.bearing_temperature", "extra": 1},
            "unknown arguments: extra",
        ),
        (
            "maximum",
            {"column": "$features.bearing_temperature"},
            "missing arguments: feature; unknown arguments: column",
        ),
        ("maximum", {"feature": "$datasets.pump_telemetry_dataset"}, "cannot bind a dataset"),
    ],
)
def test_collapse_validates_reducer_bindings(
    tmp_path: Path, function: str, args: dict, message: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["binding"] = {"function": function, "args": args}
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        Specification.from_json(path)


@pytest.mark.parametrize("legacy", ["catalog", "source", "group_by", "operations", "aggregations"])
def test_removed_aggregation_and_wrapper_schemas_are_rejected(tmp_path: Path, legacy: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    if legacy == "catalog":
        configuration["functions"]["aggregate"] = configuration["functions"].pop("collapse")
    else:
        collapse[legacy] = {}
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError):
        Specification.from_json(path)


def test_collapse_inferred_dimensions_must_exist_in_source(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["dimensions"].remove("pump")
    path = tmp_path / "invalid_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="grouping dimensions must exist in source"):
        Specification.from_json(path)


def test_collapse_catalog_requires_function_entrypoint(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["collapse"]["maximum"].pop("entrypoint")
    path = tmp_path / "missing_entrypoint.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="entrypoint"):
        Specification.from_json(path)


@pytest.mark.parametrize("container", ["object", "array"])
def test_collapse_rejects_inputs_from_multiple_datasets(tmp_path: Path, container: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    references = ["$features.bearing_temperature", "$features.health_signal_normalized"]
    value = {"inputs": references} if container == "object" else references
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["binding"]["args"]["feature"] = value
    path = tmp_path / "mixed_inputs.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="one dataset; use expand"):
        Specification.from_json(path)


def test_collapse_dimensions_alone_do_not_identify_input_dataset(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["binding"]["args"]["feature"] = "$features.pump"
    path = tmp_path / "dimension_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="must reference a source feature"):
        Specification.from_json(path)
