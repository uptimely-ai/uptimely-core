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


def test_aggregations_are_restricted_to_collapse(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["aggregations"] = {}
    missing_aggregation_path = tmp_path / "missing_aggregation.json"
    missing_aggregation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="must define aggregations"):
        Specification.from_json(missing_aggregation_path)

    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    aggregate_bindings = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]["aggregations"]
    configuration["entities"]["pump"]["datasets"][0]["mappings"]["health_signal_normalized"][
        "aggregations"
    ] = aggregate_bindings
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="vectorize mapping health_signal_normalized cannot use aggregations",
    ):
        Specification.from_json(invalid_operation_path)
