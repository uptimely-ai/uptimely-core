import json
from pathlib import Path

import pytest

from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")


def test_fragment_validation(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    # Add a valid transform (expand) to functions catalog and dataset
    configuration["functions"]["expand"] = {
        "expand_telemetry": {
            "entrypoint": "examples/example_1/functions/source.py:read_pump_telemetry",
            "args": {},
        }
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["expand"]["expand_op"] = {
        "binding": {"function": "expand_telemetry", "args": {}},
        "features": {
            "plant": {"type": "string"},
            "production_line": {"type": "string"},
            "pump": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "expanded_feature": {"type": "float", "description": "Expanded feature"},
        },
    }

    spec_path = tmp_path / "valid_transforms_spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")
    parsed_spec = Specification.from_json(spec_path)
    ds = parsed_spec.entities["pump_telemetry"].datasets[0]

    assert "read_pump_telemetry" in ds.read
    assert "expand_op" in ds.expand
    assert "expanded_feature" in ds.all_features

    # Test an unknown read function.
    bad_source_config = json.loads(json.dumps(configuration))
    bad_source_config["entities"]["pump_telemetry"]["datasets"][0]["read"]["bad_source"] = {
        "binding": {"function": "missing_read", "args": {}},
        "features": {},
    }
    bad_source_path = tmp_path / "bad_source.json"
    bad_source_path.write_text(json.dumps(bad_source_config), encoding="utf-8")
    with pytest.raises(ValueError, match="fragments reference unknown functions"):
        Specification.from_json(bad_source_path)

    # Test a fragment with an unknown function.
    bad_transform_config = json.loads(json.dumps(configuration))
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["expand"]["bad_transform"] = {
        "binding": {"function": "missing_expand", "args": {}},
        "features": {},
    }
    bad_transform_path = tmp_path / "bad_transform.json"
    bad_transform_path.write_text(json.dumps(bad_transform_config), encoding="utf-8")
    with pytest.raises(ValueError, match="fragments reference unknown functions"):
        Specification.from_json(bad_transform_path)


def test_aggregations_are_restricted_to_collapse(tmp_path: Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["collapse"]["collapse_features"] = {
        "entrypoint": "examples/example_1/functions/source.py:read_pump_telemetry",
        "args": {},
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dimensions = {
        dimension: dict(dataset["read"]["read_pump_telemetry"]["features"][dimension])
        for dimension in ("plant", "production_line", "pump", "timestamp")
    }
    dataset["collapse"]["summary"] = {
        "binding": {"function": "collapse_features", "args": {}},
        "features": dimensions,
    }
    missing_aggregation_path = tmp_path / "missing_aggregation.json"
    missing_aggregation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="must define one or more aggregations"):
        Specification.from_json(missing_aggregation_path)

    aggregation_binding = {
        "function": "pressure_flow_efficiency",
        "args": {"pressure": "$features.discharge_pressure"},
    }
    del dataset["collapse"]["summary"]
    configuration["functions"].setdefault("conform", {})["sample_telemetry"] = {
        "entrypoint": "examples/example_1/functions/source.py:read_pump_telemetry",
        "args": {},
    }
    dataset["conform"]["invalid_aggregation"] = {
        "binding": {
            "function": "sample_telemetry",
            "args": {"aggregation": aggregation_binding},
        },
        "features": dimensions,
    }
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="conform operation invalid_aggregation cannot use"):
        Specification.from_json(invalid_operation_path)
