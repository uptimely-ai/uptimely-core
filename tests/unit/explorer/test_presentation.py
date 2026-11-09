"""Tests for JSON-ready Explorer presentation data."""

import json
import pathlib

import pytest
from examples.pump_analytics.functions import analytics
from support import examples as example_support

from uptimely import project
from uptimely.explorer import presentation
from uptimely.project.build import builder


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
    assert all(
        "kind" not in function
        for function in data["catalogs"]["configuration"]["functions"].values()
    )
    assert all(
        operator["kind"] == bundle.spec_definition.operator_kinds[(profile_id, operator_id)]
        for profile_id, profile in data["catalogs"]["configuration"]["profiles"].items()
        for operator_id, operator in profile["assembly"].items()
    )
    assert data["catalogs"]["configuration"]["profiles"]["pump"]["scope"] == (
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
    assert len(merge_steps) == sum(
        invocation.role == "merge" for invocation in bundle.execution_plan.invocations
    )
    assert all(step["merge_target"] and step["fragment_source"] for step in merge_steps)
    assert all(node["merge_keys"] is not None for node in merge_nodes)
    assert all(step["role"] == "merge" and step["result"] == "target" for step in merge_steps)
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
        snapshot["catalogs"]["function_groups"]["estimate"]["operation_point_quantum_optimization"][
            "doc"
        ]["examples"]
        == examples
    )


def test_presentation_captures_project_source_in_catalog_and_snapshot(
    pump_bundle: project.BuildBundle,
) -> None:
    assert analytics.__file__ is not None
    root = pathlib.Path(analytics.__file__).resolve().parents[1]
    data = presentation.build_presentation_data(
        pump_bundle.spec_definition, pump_bundle.execution_plan, project_root=root
    )
    serialized = json.loads(presentation.serialize_presentation_data(data))
    function = serialized["catalogs"]["configuration"]["functions"]["ratio"]
    assert function["source_origin"] == "project"
    assert serialized["catalogs"]["function_groups"]["calculate"]["ratio"]["source_origin"] == (
        "project"
    )


def test_presentation_captures_installed_distribution_origin(
    pump_bundle: project.BuildBundle, tmp_path: pathlib.Path
) -> None:
    pump_bundle.spec_definition.functions["ratio"].entrypoint = "polars:thread_pool_size"

    data = presentation.build_presentation_data(
        pump_bundle.spec_definition, pump_bundle.execution_plan, project_root=tmp_path
    )
    serialized = json.loads(presentation.serialize_presentation_data(data))
    function = serialized["catalogs"]["configuration"]["functions"]["ratio"]
    assert function["source_origin"] == "third_party"
    assert function["source_distribution"] == "polars"
    assert serialized["catalogs"]["function_groups"]["calculate"]["ratio"]["source_origin"] == (
        "third_party"
    )


def test_reexport_uses_implementation_origin_not_project_module(
    pump_bundle: project.BuildBundle, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reexport_provenance_fixture.py").write_text(
        "from polars import thread_pool_size as calculate\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    pump_bundle.spec_definition.functions[
        "ratio"
    ].entrypoint = "reexport_provenance_fixture:calculate"

    data = presentation.build_presentation_data(
        pump_bundle.spec_definition, pump_bundle.execution_plan, project_root=tmp_path
    )

    function = data["catalogs"]["configuration"]["functions"]["ratio"]
    assert function["source_origin"] == "third_party"
    assert function["source_distribution"] == "polars"


def test_project_build_persists_source_origin(
    pump_bundle: project.BuildBundle, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "source_provenance_fixture.py").write_text(
        "import polars as pl\n"
        "def calculate(dataset: pl.LazyFrame, numerator_features: list[str], "
        "denominator_features: list[str], output: str, scale: float = 1.0) -> pl.LazyFrame:\n"
        "    return dataset\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    pump_bundle.spec_definition.functions[
        "ratio"
    ].entrypoint = "source_provenance_fixture:calculate"
    monkeypatch.setattr(builder, "_load_spec_definition", lambda *args: pump_bundle.spec_definition)

    project.build_project(tmp_path)

    snapshot = json.loads((tmp_path / project.EXPLORER_DATA_FILE).read_text(encoding="utf-8"))
    assert snapshot["catalogs"]["configuration"]["functions"]["ratio"]["source_origin"] == "project"
    assert snapshot["catalogs"]["function_groups"]["calculate"]["ratio"]["source_origin"] == (
        "project"
    )
