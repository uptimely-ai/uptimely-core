import json
import pathlib

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import spec
from uptimely.spec import model as spec_model
from uptimely.spec import references
from uptimely.spec.python import bind, conversion, dataset, feature, mapping, ref
from uptimely.spec.validation import context
from uptimely.spec.validation import errors as validation_errors

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def _escape_configuration() -> dict:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["external_action"] = {
        "operation": "escape",
        "returns": "any",
        "entrypoint": "examples.pump_analytics.functions.calculation:maximum",
        "args": {"source": {"type": "dataframe"}},
    }
    target = configuration["entities"]["pump_telemetry"]["datasets"][0]
    target["features"].update(
        {
            "external_first": {"type": "float"},
            "external_second": {"type": "float"},
            "external_third": {"type": "float"},
        }
    )
    target["mappings"]["escape_first"] = {
        "binding": {
            "function": "external_action",
            "args": {"source": "$datasets.pump_dataset.dataframe"},
        },
        "features": {
            "inputs": [
                "$features.bearing_temperature",
                "$features.health_signal_normalized",
                "$features.pump",
            ],
            "outputs": ["$features.external_first", "$features.external_second"],
        },
    }
    target["mappings"]["escape_second"] = {
        "binding": {
            "function": "external_action",
            "args": {"source": "$datasets.pump_dataset.dataframe"},
        },
        "features": {
            "inputs": ["$features.external_first"],
            "outputs": ["$features.external_third"],
        },
    }
    return configuration


def test_mapping_locations_preserve_keys_duplicates_and_unresolved_functions() -> None:
    model = spec_model.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    entity_id = next(iter(model.entities))
    entity = model.entities[entity_id]
    dataset = entity.datasets[0]
    mapping = next(iter(dataset.mappings.values()))
    dataset.mappings["alias"] = mapping
    mapping.binding.function = "missing"
    entity.datasets.append(dataset.model_copy(deep=True))

    locations = list(context.SpecValidationContext.build(model).iter_mappings())
    declarations = list(references.iter_mapping_items(model))
    actual = [(item.entity_id, item.dataset, item.mapping_id, item.mapping) for item in locations]
    assert actual == declarations
    aliases = [item for item in locations if item.mapping_id == "alias"]
    assert len(aliases) == 2
    assert aliases[0].mapping is mapping
    assert aliases[0].key == (entity_id, dataset.id, "alias")
    assert aliases[0].path[-1] == mapping.id
    assert aliases[0].mapping_id != mapping.id
    same_dataset_locations = [item for item in locations if item.dataset is dataset]
    assert len(same_dataset_locations) > 1
    assert all(
        item.dataset_location is same_dataset_locations[0].dataset_location
        for item in same_dataset_locations
    )
    assert list(references.iter_mappings(model)) == [
        (item.entity_id, item.dataset, item.mapping) for item in locations
    ]

    facts = [
        item
        for item in context.SpecValidationContext.build(model).mappings
        if item.location.dataset is dataset
    ]
    dimensions = frozenset(entity.dimension_ids)
    assert facts
    assert all(item.dimensions == dimensions for item in facts)
    assert all(item.local_features == frozenset(dataset.features) | dimensions for item in facts)


def test_validation_context_retains_duplicate_index_candidates() -> None:
    model = spec_model.Spec.model_validate(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    pump_dataset = model.entities["pump"].datasets[0]
    model.entities["pump"].datasets.append(pump_dataset.model_copy(deep=True))

    validation_context = context.SpecValidationContext.build(model)

    assert len(validation_context.datasets_by_id[pump_dataset.id]) == 2
    feature_id = next(
        feature_id
        for feature_id in pump_dataset.features
        if feature_id not in validation_context.dimension_ids
    )
    assert len(validation_context.feature_owners[feature_id]) == 2


@pytest.mark.parametrize(
    "document",
    [
        {"spec_version": "0.1.0"},
        {
            "spec_version": "0.2.0",
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
        spec.load_spec(path)


def test_mapping_validation(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "operation": "expand",
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.source:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
            "target": {"type": "dataframe"},
        },
    }
    dataset = configuration["entities"]["pump_telemetry"]["datasets"][0]
    dataset["features"]["expanded_feature"] = {"type": "float", "description": "Expanded feature"}
    dataset["mappings"]["expand_op"] = {
        "binding": {
            "function": "expand_telemetry",
            "args": {
                "source": "$datasets.pump_dataset.dataframe",
                "target": "$datasets.@.dataframe",
            },
        },
        "features": {
            "inputs": ["$features.bearing_temperature_max"],
            "outputs": ["$features.expanded_feature"],
        },
    }

    spec_path = tmp_path / "valid_mappings_spec.json"
    spec_path.write_text(json.dumps(configuration), encoding="utf-8")
    parsed_spec = spec.load_spec(spec_path)
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
        "features": {"inputs": [], "outputs": ["$features.bad_source_feature"]},
    }
    bad_source_path = tmp_path / "bad_source.json"
    bad_source_path.write_text(json.dumps(bad_source_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        spec.load_spec(bad_source_path)

    bad_transform_config = json.loads(json.dumps(configuration))
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["features"][
        "bad_transform_feature"
    ] = {"type": "float"}
    bad_transform_config["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "bad_transform"
    ] = {
        "binding": {"function": "missing_expand", "args": {}},
        "features": {
            "inputs": ["$features.bearing_temperature_max"],
            "outputs": ["$features.bad_transform_feature"],
        },
    }
    bad_transform_path = tmp_path / "bad_transform.json"
    bad_transform_path.write_text(json.dumps(bad_transform_config), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings reference unknown functions"):
        spec.load_spec(bad_transform_path)


def test_escape_mappings_support_cross_dataset_multi_feature_dependencies_and_chains(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "escape.json"
    path.write_text(json.dumps(_escape_configuration()), encoding="utf-8")

    parsed_spec = spec.load_spec(path)
    mappings = parsed_spec.entities["pump_telemetry"].datasets[0].mappings

    assert mappings["escape_first"].input_features == [
        "bearing_temperature",
        "health_signal_normalized",
        "pump",
    ]
    assert mappings["escape_first"].output_features == ["external_first", "external_second"]
    assert mappings["escape_second"].input_features == ["external_first"]
    assert mappings["escape_second"].output_features == ["external_third"]


@pytest.mark.parametrize(
    ("field", "value", "message", "error_code", "path_suffix"),
    [
        (
            "inputs",
            [],
            "Escape mappings must declare one or more input features",
            "invalid_mapping_feature_inputs",
            ("features", "inputs"),
        ),
        (
            "outputs",
            [],
            "Mapping escape_first must declare one or more features",
            None,
            None,
        ),
        (
            "inputs",
            ["$features.unknown_feature"],
            "Mapping escape_first references unknown input feature: unknown_feature",
            None,
            None,
        ),
    ],
)
def test_escape_mappings_require_declared_inputs_and_outputs(
    tmp_path: pathlib.Path,
    field: str,
    value: list[str],
    message: str,
    error_code: str | None,
    path_suffix: tuple[str, ...] | None,
) -> None:
    configuration = _escape_configuration()
    mapping_definition = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"][
        "escape_first"
    ]
    mapping_definition["features"][field] = value
    path = tmp_path / "invalid_escape.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match=message) as error:
        spec.load_spec(path)

    if error_code is not None:
        assert isinstance(error.value, validation_errors.SpecError)
        assert error.value.code == error_code
        assert error.value.path[-2:] == path_suffix


def test_escape_mappings_reject_duplicate_feature_producers(tmp_path: pathlib.Path) -> None:
    configuration = _escape_configuration()
    mappings = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]
    duplicate = json.loads(json.dumps(mappings["escape_first"]))
    duplicate["features"]["outputs"] = ["$features.external_first"]
    mappings["escape_duplicate"] = duplicate
    path = tmp_path / "duplicate_escape.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Feature external_first is produced by multiple mappings"):
        spec.load_spec(path)


def test_escape_dependencies_reject_cycles(tmp_path: pathlib.Path) -> None:
    configuration = _escape_configuration()
    first = configuration["entities"]["pump_telemetry"]["datasets"][0]["mappings"]["escape_first"]
    first["features"]["inputs"] = ["$features.external_third"]
    path = tmp_path / "escape_cycle.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="Mapping feature dependency cycle"):
        spec.load_spec(path)


def test_python_conversion_and_json_loading_share_escape_input_validation(
    tmp_path: pathlib.Path,
) -> None:
    declaration = dataset.Dataset(
        id="observations",
        mappings=[
            mapping.Mapping(
                id="escape",
                bind=bind.bind(ref.function("example:escape", operation="escape")),
                outputs=[feature.Feature(id="external_result")],
            )
        ],
    )
    expected_message = (
        "entities.entity.datasets.observations.mappings.escape.features.inputs: "
        "Escape mappings must declare one or more input features"
    )

    with pytest.raises(
        validation_errors.SpecError, match="Escape mappings must declare"
    ) as python_error:
        spec.from_python(datasets=[declaration])

    path = tmp_path / "python_escape.json"
    path.write_text(json.dumps(conversion.to_dict(datasets=[declaration])), encoding="utf-8")
    with pytest.raises(
        validation_errors.SpecError, match="Escape mappings must declare"
    ) as json_error:
        spec.load_spec(path)

    assert str(python_error.value) == expected_message
    assert str(json_error.value) == expected_message
    assert python_error.value.code == json_error.value.code == "invalid_mapping_feature_inputs"


def test_expand_mapping_requires_lower_dimensional_feature_input(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["expand_telemetry"] = {
        "operation": "expand",
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.source:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
            "target": {"type": "dataframe"},
        },
    }
    target = configuration["entities"]["pump_telemetry"]["datasets"][0]
    target["features"]["expanded_feature"] = {"type": "float"}
    target["mappings"]["expand_op"] = {
        "binding": {
            "function": "expand_telemetry",
            "args": {
                "source": "$datasets.pump_dataset.dataframe",
                "target": "$datasets.@.dataframe",
            },
        },
        "features": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.expanded_feature"],
        },
    }
    path = tmp_path / "invalid_expand_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="declared feature from a lower-dimensional dataset"):
        spec.load_spec(path)


def test_conform_mapping_requires_matching_input_dimensions(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["conform_telemetry"] = {
        "operation": "conform",
        "returns": "dataframe",
        "entrypoint": "examples.pump_analytics.functions.source:read_pump_telemetry",
        "args": {
            "source": {"type": "dataframe"},
            "target": {"type": "dataframe"},
        },
    }
    target = configuration["entities"]["pump"]["datasets"][0]
    target["features"]["conformed_feature"] = {"type": "float"}
    target["mappings"]["conform_op"] = {
        "binding": {
            "function": "conform_telemetry",
            "args": {
                "source": "$datasets.pump_telemetry_dataset.dataframe",
                "target": "$datasets.@.dataframe",
            },
        },
        "features": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.conformed_feature"],
        },
    }
    path = tmp_path / "invalid_conform_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="must preserve target dimensionality"):
        spec.load_spec(path)


@pytest.mark.parametrize("mapping_id", ["bearing_temperature_by_pump", "health_signal_normalized"])
def test_mapping_rejects_explicit_source(tmp_path: pathlib.Path, mapping_id: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump"]["datasets"][0]["mappings"][mapping_id]["source"] = (
        "$datasets.pump_telemetry_dataset"
    )
    invalid_operation_path = tmp_path / "invalid_aggregation_operation.json"
    invalid_operation_path.write_text(json.dumps(configuration), encoding="utf-8")

    with pytest.raises(ValueError, match="source"):
        spec.load_spec(invalid_operation_path)


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
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


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
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = inputs
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


@pytest.mark.parametrize("legacy", ["catalog", "source", "group_by", "operations", "aggregations"])
def test_removed_aggregation_and_wrapper_schemas_are_rejected(
    tmp_path: pathlib.Path, legacy: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
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
        spec.load_spec(path)


def test_collapse_inferred_dimensions_must_exist_in_source(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["entities"]["pump_telemetry"]["dimensions"].remove("pump")
    path = tmp_path / "invalid_dimensions.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="grouping dimensions must exist in source"):
        spec.load_spec(path)


def test_collapse_catalog_requires_function_entrypoint(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["functions"]["maximum"].pop("entrypoint")
    path = tmp_path / "missing_entrypoint.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="entrypoint"):
        spec.load_spec(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("returns", "none", "must declare returns=dataframe"),
        ("args", {}, "requires 1 dataframe argument"),
    ],
)
def test_function_contract_validates_operation_inputs_and_return(
    tmp_path: pathlib.Path, field: str, value: object, message: str
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if field == "returns":
        configuration["functions"]["maximum"][field] = value
    else:
        configuration["functions"]["unmapped_vectorize"] = {
            "operation": "vectorize",
            "returns": "dataframe",
            "entrypoint": "examples.pump_analytics.functions.calculation:maximum",
            "args": value,
        }
    path = tmp_path / "invalid_function_contract.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        spec.load_spec(path)


def test_collapse_rejects_inputs_from_multiple_datasets(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    references = ["$features.bearing_temperature", "$features.health_signal_normalized"]
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = references
    path = tmp_path / "mixed_inputs.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="one dataset; use expand"):
        spec.load_spec(path)


def test_collapse_dimensions_alone_do_not_identify_input_dataset(
    tmp_path: pathlib.Path,
) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    collapse = configuration["entities"]["pump"]["datasets"][0]["mappings"][
        "bearing_temperature_by_pump"
    ]
    collapse["features"]["inputs"] = ["$features.pump"]
    path = tmp_path / "dimension_input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    with pytest.raises(ValueError, match="must reference a source feature"):
        spec.load_spec(path)
