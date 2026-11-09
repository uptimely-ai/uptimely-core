"""Tests for JSON-ready Explorer presentation data."""

import json
import pathlib

from support import examples as example_support

from uptimely import project
from uptimely.explorer import presentation


def test_build_presentation_data_returns_versioned_json_structures(
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    bundle = example_bundle_factory(features=("health_signal_normalized",))

    data = presentation.build_presentation_data(
        bundle.spec_definition,
        bundle.execution_plan,
        features=["health_signal_normalized"],
    )
    serialized = json.dumps(data)

    assert data["format_version"] == presentation.EXPLORER_FORMAT_VERSION
    assert data["project"]["name"] == bundle.spec_definition.name
    assert data["scope"]["features"] == ["health_signal_normalized"]
    assert data["scope"]["is_scoped"]
    assert data["catalogs"]["configuration"]
    assert data["catalogs"]["configuration"]["profiles"]["pump_profile"]["scope"] == (
        "Pump-level telemetry and external workflow inputs"
    )
    assert data["graphs"]["feature_lineage"]["nodes"]
    assert data["graphs"]["invocation_lineage"]["nodes"]
    assert data["plan"]["stage_count"] == len(bundle.execution_plan.execution_stages)
    assert data["stages"]
    assert data["animation"]["stages"]
    merge_steps = [
        step for stage in data["stages"] for step in stage["steps"] if step["phase"] == "merge"
    ]
    merge_nodes = [
        node for node in data["graphs"]["invocation_lineage"]["nodes"] if node["phase"] == "merge"
    ]
    assert merge_steps
    assert merge_nodes
    assert dict(data["plan"]["function_kind_counts"])["merge"] == len(merge_steps)
    assert all(step["merge_target"] and step["fragment_source"] for step in merge_steps)
    assert all(node["merge_keys"] is not None for node in merge_nodes)
    assert any(
        link["dependency_type"] == "fragment"
        for link in data["graphs"]["invocation_lineage"]["links"]
    )
    assert "graph_data" not in serialized
    assert "invocation_lineage_data" not in serialized


def test_build_snapshot_preserves_complete_function_example(
    example_projects: pathlib.Path,
) -> None:
    snapshot = json.loads(
        (example_projects / "pump_analytics" / project.EXPLORER_DATA_FILE).read_text(
            encoding="utf-8"
        )
    )
    configuration = snapshot["catalogs"]["configuration"]["functions"]
    function = configuration["operation_point_quantum_optimization"]
    examples = function["doc"]["examples"]

    assert len(examples) == 1
    assert examples[0].startswith('frame = pl.LazyFrame(\n    {"pressure":')
    assert '\n)\nfeatures = ["pressure", "flow", "power", "temp", "vib"]\n' in examples[0]
    assert examples[0].endswith('["converged"]\nTrue')
    assert (
        snapshot["catalogs"]["function_groups"]["vectorize"][
            "operation_point_quantum_optimization"
        ]["doc"]["examples"]
        == examples
    )
