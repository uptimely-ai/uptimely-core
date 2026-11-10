"""Profile relation declarations and their portable representation."""

import polars as pl
import pytest
from support import execution as execution_support

from uptimely.compiler import compiler
from uptimely.spec import model, serialization, validation
from uptimely.spec.python import assembly, conversion, dimension, feature, merge, profile, ref
from uptimely.spec.validation import errors


def _dimension() -> dimension.Dimension:
    return dimension.Dimension(
        id="machine",
        resolutions=[
            dimension.Resolution(id="pump", key="pump_id", type="string", parent="series"),
            dimension.Resolution(id="series", key="series_id", type="string"),
        ],
    )


def _read_related() -> pl.DataFrame:
    return pl.DataFrame({"pump_id": ["pump"], "plant_id": ["plant"], "value": [1.0]})


def test_compiled_relation_from_non_grain_dimension_survives_execution(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    machines = _dimension()
    sites = dimension.Dimension(
        id="site",
        resolutions=[dimension.Resolution(id="plant", key="plant_id", type="string")],
    )
    declaration = profile.Profile(
        id="readings",
        grain=[machines.resolution("pump")],
        relations=[sites.resolution("plant")],
        assembly=[
            assembly.Operator(
                id="read",
                interface=assembly.Interface(outputs=[feature.Feature(id="value", type="float")]),
                compute=assembly.Binding(
                    function=ref.function(_read_related, returns="dataframe"),
                ),
                merge=merge.default(),
            )
        ],
    )
    document = conversion.to_model([declaration])
    plan = compiler.Compiler().compile(document, features=["value"])
    compute = next(invocation for invocation in plan.invocations if invocation.role == "compute")
    assert compute.target_identifiers == ["pump_id"]
    assert "plant_id" in compute.fragment_keys
    assert compute.column_types["plant_id"] == "string"
    assert "plant_id" not in compute.output_features
    assert compute.output_features == ["value"]
    assert document.profiles["readings"].assembly["read"].output_features == ["value"]
    assert set(document.profiles["readings"].features) == {"value"}
    result = engine_for_plan(plan, spec_definition=document).run(validate=True)
    assert not result.failures
    assert result.datasets["readings"].to_dicts() == [
        {"pump_id": "pump", "value": 1.0, "plant_id": "plant"}
    ]


@pytest.mark.parametrize("column", ["pump_id", "series_id"])
@pytest.mark.parametrize("field", ["inputs", "outputs"])
def test_key_interface_references_are_rejected_with_path(column: str, field: str) -> None:
    document = model.Spec.model_validate(
        {
            "dimensions": {"machine": _dimension().to_model()},
            "functions": {
                "read": {"entrypoint": f"{__name__}:_read_related", "returns": "dataframe"}
            },
            "profiles": {
                "readings": {
                    "grain": [{"dimension": "machine", "resolution": "pump"}],
                    "relations": [{"dimension": "machine", "resolution": "series"}],
                    "features": {"value": {}},
                    "assembly": {
                        "read": {
                            "compute": {"function": "read"},
                            "interface": {
                                "inputs": [f"$features.{column}"] if field == "inputs" else [],
                                "outputs": [f"$features.{column}"]
                                if field == "outputs"
                                else ["$features.value"],
                            },
                        }
                    },
                }
            },
        }
    )
    restored = model.Spec.model_validate(serialization.to_document(document))
    with pytest.raises(errors.SpecError, match="must contain only features") as caught:
        validation.validate_spec(restored)
    assert caught.value.code == "interface_key_reference"
    assert caught.value.path == ("profiles", "readings", "assembly", "read", "interface", field, 0)


def _copy_related(
    dataset: pl.DataFrame, identifier: str, relation: str, value: str, output: str
) -> pl.DataFrame:
    return dataset.select(identifier, relation, pl.col(value).alias(output))


def test_inferred_inputs_exclude_local_and_foreign_keys() -> None:
    machines = _dimension()
    source = profile.Profile(
        id="source",
        grain=[machines.resolution("pump")],
        relations=[machines.resolution("series")],
        assembly=[
            assembly.Operator(
                id="read",
                interface=assembly.Interface(outputs=[feature.Feature(id="value")]),
                compute=assembly.Binding(function=ref.function(_read_related)),
            )
        ],
    )
    target = profile.Profile(
        id="target",
        grain=[machines.resolution("pump")],
        assembly=[
            assembly.Operator(
                id="copy",
                interface=assembly.Interface(outputs=[feature.Feature(id="copied")]),
                compute=assembly.Binding(
                    function=ref.function(_copy_related),
                    arguments={
                        "dataset": source.dataset,
                        "identifier": ref.feature("pump_id"),
                        "relation": ref.feature("series_id"),
                        "value": ref.feature("value"),
                        "output": ref.feature("copied").id,
                    },
                ),
            )
        ],
    )
    assert "pump_id" not in target.to_model().assembly["copy"].input_features
    document = conversion.to_model([source, target])
    validation.validate_spec(document)
    assert document.profiles["target"].assembly["copy"].input_features == ["value"]
    compiled = compiler.Compiler().compile(document, features=["copied"])
    invocation = next(item for item in compiled.invocations if item.operator_id == "copy")
    assert invocation.input_features == ["value"]
    assert invocation.output_features == ["copied"]
    assert invocation.arguments["identifier"] == "pump_id"
    assert invocation.arguments["relation"] == "series_id"


@pytest.mark.parametrize("staged", [False, True])
def test_key_only_reader_has_no_feature_outputs(
    engine_for_plan: execution_support.EngineFactory,
    staged: bool,
) -> None:
    machines = _dimension()
    sites = dimension.Dimension(
        id="site",
        resolutions=[dimension.Resolution(id="plant", key="plant_id", type="string")],
    )
    declaration = profile.Profile(
        id="keys_only",
        grain=[machines.resolution("pump")],
        relations=[sites.resolution("plant")],
        assembly=[
            assembly.Operator(
                id="read",
                interface=assembly.Interface(),
                compute=assembly.Binding(function=ref.function(_read_related)),
                merge=merge.default() if staged else None,
            )
        ],
    )
    document = conversion.to_model([declaration])
    validation.validate_spec(document)
    compiled = compiler.Compiler().compile(document)
    assert document.profiles["keys_only"].features == {}
    assert all(not invocation.output_features for invocation in compiled.invocations)
    execution = engine_for_plan(compiled, spec_definition=document).run(validate=True)
    assert not execution.failures
    assert execution.datasets["keys_only"].to_dicts() == [{"pump_id": "pump", "plant_id": "plant"}]


def test_relations_round_trip_without_changing_grain_or_features() -> None:
    machines = _dimension()
    sites = dimension.Dimension(
        id="site",
        resolutions=[dimension.Resolution(id="plant", key="plant_id", type="string")],
    )
    declaration = profile.Profile(
        id="readings",
        grain=[machines.resolution("pump")],
        relations=[machines.resolution("series"), sites.resolution("plant")],
    )
    document = conversion.to_model([declaration])
    validation.validate_spec(document)
    restored = model.Spec.model_validate(serialization.to_document(document))

    assert restored == document
    assert set(document.dimensions) == {"machine", "site"}
    assert document.identifiers_by_profile["readings"] == ["pump_id"]
    assert document.key_ids_by_profile["readings"] == {
        "pump_id",
        "series_id",
        "plant_id",
    }
    assert document.profiles["readings"].features == {}
    assert declaration.identifier_types == {"pump_id": "string"}
    assert declaration.relation_types == {"series_id": "string", "plant_id": "string"}
    assert declaration.identifiers == ["pump_id"]
    assert declaration.keys == ["pump_id", "series_id", "plant_id"]
    assert declaration.key_types == document.key_types_by_profile["readings"]
    assert document.relation_types_by_profile["readings"] == declaration.relation_types
    assert document.identifier_ids == {"pump_id"}
    assert serialization.to_document(document)["profiles"]["readings"]["relations"] == [
        {"dimension": "machine", "resolution": "series"},
        {"dimension": "site", "resolution": "plant"},
    ]


def test_relation_only_dimension_is_collected() -> None:
    machines = _dimension()

    class Related(profile.Profile):
        relations = [machines.resolution("series")]

    document = conversion.to_model([Related()])
    validation.validate_spec(document)
    assert document.identifiers_by_profile["related"] == []
    assert document.key_types_by_profile["related"] == {"series_id": "string"}
    assert document.profiles["related"].identifiers(document.dimensions) == []
    assert Related().identifiers == []
    assert Related().identifier_types == {}
    assert Related().keys == ["series_id"]
    assert Related().key_types == {"series_id": "string"}
    assert Related().relation_types == {"series_id": "string"}


@pytest.mark.parametrize(
    ("relations", "features", "code"),
    [
        ([{"dimension": "missing", "resolution": "series"}], {}, "unknown_relation_dimension"),
        ([{"dimension": "machine", "resolution": "missing"}], {}, "unknown_relation_resolution"),
        ([{"dimension": "machine", "resolution": "pump"}], {}, "duplicate_relation_column"),
        (
            [{"dimension": "machine", "resolution": "series"}] * 2,
            {},
            "duplicate_relation_column",
        ),
        (
            [{"dimension": "machine", "resolution": "series"}],
            {"series_id": {}},
            "relation_feature_collision",
        ),
    ],
)
def test_invalid_relations_report_spec_path(
    relations: list[dict[str, str]], features: dict[str, dict], code: str
) -> None:
    document = model.Spec.model_validate(
        {
            "dimensions": {"machine": _dimension().to_model()},
            "profiles": {
                "readings": {
                    "grain": [{"dimension": "machine", "resolution": "pump"}],
                    "relations": relations,
                    "features": features,
                }
            },
        }
    )
    with pytest.raises(errors.SpecError) as caught:
        validation.validate_spec(document)
    assert caught.value.code == code
    assert caught.value.path[:3] == ("profiles", "readings", "relations")


@pytest.mark.parametrize("relations", ["series", [object()]])
def test_invalid_python_relations_are_rejected(
    relations: list[dimension.Resolution],
) -> None:
    with pytest.raises(TypeError, match="relations"):
        declaration = profile.Profile(id="readings", relations=relations)
        declaration.to_model()
