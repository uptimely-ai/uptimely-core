"""Tests for JSON-ready Explorer presentation data."""

import json

from support import examples as example_support

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
        "Telemetry available to the source profile"
    )
    assert data["graphs"]["feature_lineage"]["nodes"]
    assert data["graphs"]["invocation_lineage"]["nodes"]
    assert data["plan"]["stage_count"] == len(bundle.execution_plan.execution_stages)
    assert data["stages"]
    assert data["animation"]["stages"]
    assert "graph_data" not in serialized
    assert "invocation_lineage_data" not in serialized
