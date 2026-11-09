import copy
import typing

import pydantic
import pytest

from uptimely.spec import model
from uptimely.spec.python import Profile, Resolution, Spec
from uptimely.spec.python import dimension as dimension_api
from uptimely.spec.python.dimension import Dimension
from uptimely.spec.validation import errors, validate_spec
from uptimely.spec.validation.rules import profiles as profile_rules
from uptimely.spec.validation.rules import row_context as row_context_rules
from uptimely.spec.validation.rules.operators import contracts

Document = dict[str, typing.Any]


def test_resolution_display_name_survives_python_and_document_serialization() -> None:
    resolution = dimension_api.Resolution(
        id="pump", key="pump_id", type="string", name="Individual pump"
    )
    dimension = dimension_api.Dimension(id="machine", resolutions=[resolution])
    parsed = dimension.to_model()

    assert dimension.resolution("pump").name == "Individual pump"
    assert parsed.resolutions["pump"].name == "Individual pump"
    serialized = parsed.model_dump(exclude_none=True)
    assert serialized["resolutions"]["pump"]["name"] == "Individual pump"
    document = _document()
    document["dimensions"]["machine"]["resolutions"]["pump"]["name"] = "Individual pump"
    assert _validate(document).dimensions["machine"].resolutions["pump"].name == ("Individual pump")


def _document() -> Document:
    return {
        "dimensions": {
            "machine": {
                "resolutions": {
                    "pump": {"key": "pump_id", "type": "string", "parent": "fleet"},
                    "fleet": {"key": "fleet_id", "type": "string"},
                }
            },
            "sales_time": {"resolutions": {"default": {"key": "sales_date", "type": "datetime"}}},
            "measurement_time": {
                "resolutions": {
                    "default": {"key": "timestamp", "type": "datetime"},
                    "index": {"key": "step_index", "type": "integer"},
                }
            },
        },
        "profiles": {
            "pump_telemetry": {
                "scope": "One row per pump observation",
                "grain": [
                    {"dimension": "machine", "resolution": "pump"},
                    {"dimension": "sales_time", "resolution": "default"},
                    {"dimension": "measurement_time", "resolution": "default"},
                ],
                "order": [
                    {
                        "dimension": "measurement_time",
                        "resolution": "default",
                        "direction": "asc",
                    }
                ],
            },
            "fleet_summary": {"grain": [{"dimension": "machine", "resolution": "fleet"}]},
        },
    }


def _validate(document: Document) -> model.Spec:
    parsed = model.Spec.model_validate(document)
    validate_spec(parsed)
    return parsed


def test_profile_grain_selects_available_resolutions_in_key_order() -> None:
    parsed = _validate(_document())

    assert parsed.profiles["pump_telemetry"].dimension_ids == [
        "machine",
        "sales_time",
        "measurement_time",
    ]
    assert parsed.profiles["fleet_summary"].grain[0].resolution == "fleet"
    assert parsed.dimensions["machine"].resolutions["pump"].parent == "fleet"
    assert ("sales_time", "default") in parsed.profiles["pump_telemetry"].grain_reference_set
    assert (
        "measurement_time",
        "default",
    ) in parsed.profiles["pump_telemetry"].grain_reference_set


def test_serialization_keeps_resolution_grain_and_order_references() -> None:
    parsed = model.Spec.model_validate(_document())
    serialized = parsed.model_dump(exclude_none=True)

    assert serialized["dimensions"]["machine"]["resolutions"]["pump"] == {
        "key": "pump_id",
        "type": "string",
        "parent": "fleet",
    }
    assert serialized["profiles"]["pump_telemetry"]["grain"][0] == {
        "dimension": "machine",
        "resolution": "pump",
    }
    assert "dimensions" not in serialized["profiles"]["pump_telemetry"]
    assert serialized["profiles"]["pump_telemetry"]["scope"] == "One row per pump observation"


@pytest.mark.parametrize(
    "legacy_field",
    ["dimensions", "row_scope"],
)
def test_profile_rejects_removed_dimension_and_descriptive_grain_fields(
    legacy_field: str,
) -> None:
    document = _document()
    document["profiles"]["pump_telemetry"][legacy_field] = (
        ["machine"] if legacy_field == "dimensions" else {"grain": "One row per pump"}
    )

    with pytest.raises(pydantic.ValidationError):
        model.Spec.model_validate(document)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"].append(
                {"dimension": "machine", "resolution": "fleet"}
            ),
            "duplicate_grain_dimension",
        ),
        (
            lambda doc: doc["dimensions"]["measurement_time"]["resolutions"]["default"].update(
                {"key": "pump_id"}
            ),
            "duplicate_grain_key",
        ),
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"][0].update(
                {"resolution": "missing"}
            ),
            "unknown_grain_resolution",
        ),
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"][0].update(
                {"dimension": "missing"}
            ),
            "unknown_grain_dimension",
        ),
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["order"][0].update(
                {"resolution": "missing"}
            ),
            "invalid_order_resolution",
        ),
    ],
)
def test_invalid_grain_and_order_references_are_rejected(
    mutate: typing.Callable[[Document], None], code: str
) -> None:
    document = copy.deepcopy(_document())
    mutate(document)

    with pytest.raises(errors.SpecError) as error:
        _validate(document)

    assert error.value.code == code


@pytest.mark.parametrize(
    ("mutate", "validate", "code"),
    [
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"][0].update(
                {"dimension": "missing"}
            ),
            profile_rules.validate_grain_dimensions,
            "unknown_grain_dimension",
        ),
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"].append(
                {"dimension": "machine", "resolution": "fleet"}
            ),
            profile_rules.validate_unique_grain_dimensions,
            "duplicate_grain_dimension",
        ),
        (
            lambda doc: doc["profiles"]["pump_telemetry"]["grain"][0].update(
                {"resolution": "missing"}
            ),
            profile_rules.validate_grain_resolutions,
            "unknown_grain_resolution",
        ),
        (
            lambda doc: doc["dimensions"]["measurement_time"]["resolutions"]["default"].update(
                {"key": "pump_id"}
            ),
            profile_rules.validate_unique_grain_keys,
            "duplicate_grain_key",
        ),
    ],
)
def test_grain_validators_enforce_one_invariant_each(
    mutate: typing.Callable[[Document], None],
    validate: typing.Callable[[model.Spec], None],
    code: str,
) -> None:
    document = copy.deepcopy(_document())
    mutate(document)
    parsed = model.Spec.model_validate(document)

    with pytest.raises(errors.SpecError) as error:
        validate(parsed)

    assert error.value.code == code


def test_duplicate_order_reference_is_rejected() -> None:
    document = _document()
    document["profiles"]["pump_telemetry"]["order"].append(
        document["profiles"]["pump_telemetry"]["order"][0].copy()
    )

    with pytest.raises(errors.SpecError, match="order repeats dimension"):
        _validate(document)


def test_resolution_parent_must_be_local_and_acyclic() -> None:
    document = _document()
    document["dimensions"]["machine"]["resolutions"]["pump"]["parent"] = "day"
    with pytest.raises(ValueError, match="unknown parent resolution"):
        _validate(document)


def _collapse_spec(target_resolution: str) -> model.Spec:
    return model.Spec.model_validate(
        {
            "dimensions": {
                "machine": {
                    "resolutions": {
                        "machine": {
                            "key": "machine_id",
                            "type": "string",
                            "parent": "fleet",
                        },
                        "fleet": {
                            "key": "fleet_id",
                            "type": "string",
                        },
                        "line": {
                            "key": "line_id",
                            "type": "string",
                        },
                    }
                }
            },
            "functions": {
                "collapse": {
                    "kind": "collapse",
                    "returns": "dataframe",
                    "entrypoint": "example:collapse",
                    "args": {"data": {"type": "dataframe"}},
                }
            },
            "profiles": {
                "source": {
                    "grain": [{"dimension": "machine", "resolution": "machine"}],
                    "features": {"temperature": {}},
                },
                "target": {
                    "grain": [{"dimension": "machine", "resolution": target_resolution}],
                    "features": {"maximum": {}},
                    "assembly": {
                        "maximum": {
                            "compute": {
                                "function": "collapse",
                                "args": {"data": "$profiles.source.dataset"},
                            },
                            "interface": {
                                "inputs": ["$features.temperature"],
                                "outputs": ["$features.maximum"],
                            },
                        }
                    },
                },
            },
        }
    )


def test_collapse_accepts_a_target_resolution_in_the_source_parent_chain() -> None:
    document = _collapse_spec("fleet")

    assert document.grain_refines("target", "source")
    assert contracts.validate_dimension_change(document) is None


def test_collapse_rejects_an_unrelated_target_resolution() -> None:
    document = _collapse_spec("line")

    assert not document.grain_refines("target", "source")
    with pytest.raises(ValueError, match="strictly higher dimensionality"):
        contracts.validate_dimension_change(document)


def test_python_spec_infers_dimensions_and_resolutions_from_profile_grain() -> None:
    machine = Dimension(
        id="machine",
        resolutions=[
            Resolution(id="machine", key="machine_id", type="string"),
            Resolution(id="fleet", key="fleet_id", type="string"),
        ],
    )
    profiles = [
        Profile(id="machine_readings", grain=[machine.resolution("machine")]),
        Profile(id="fleet_summary", grain=[machine.resolution("fleet")]),
    ]

    document = Spec(profiles=profiles).to_model()

    assert list(document.dimensions) == ["machine"]
    assert list(document.dimensions["machine"].resolutions) == ["machine", "fleet"]
    assert [item.resolution for item in document.profiles["machine_readings"].grain] == ["machine"]


def test_python_spec_rejects_conflicting_or_unresolved_grain_declarations() -> None:
    first = Dimension(
        id="machine",
        resolutions=[Resolution(id="machine", key="machine_id", type="string")],
    )
    conflict = Dimension(
        id="machine",
        resolutions=[Resolution(id="machine", key="other_id", type="string")],
    )
    with pytest.raises(ValueError, match="Conflicting metadata for dimension 'machine'"):
        Spec(
            profiles=[
                Profile(id="first", grain=[first.resolution("machine")]),
                Profile(id="second", grain=[conflict.resolution("machine")]),
            ]
        ).to_model()

    with pytest.raises(ValueError, match="does not declare resolution 'missing'"):
        Spec(profiles=[Profile(id="missing", grain=[first.resolution("missing")])]).to_model()

    document = _document()
    document["dimensions"]["machine"]["resolutions"]["fleet"]["parent"] = "pump"
    with pytest.raises(errors.SpecError, match="resolution parent cycle"):
        _validate(document)


@pytest.mark.parametrize(
    ("resolution_id", "measurement", "expected_error"),
    [
        ("default", {"time": "1h"}, None),
        ("default", {"steps": 1}, "integer"),
        ("index", {"steps": 1}, None),
        ("index", {"time": "1h"}, "datetime"),
    ],
)
def test_row_context_uses_the_selected_resolution_type(
    resolution_id: str,
    measurement: dict[str, str | int],
    expected_error: str | None,
) -> None:
    document = _document()
    document["profiles"]["pump_telemetry"]["grain"][2]["resolution"] = resolution_id
    document["profiles"]["pump_telemetry"]["assembly"] = {
        "contextual": {
            "compute": {"function": "contextual", "args": {}},
            "row_context": {
                "dimension": "$dimensions.measurement_time",
                "before": measurement,
            },
        }
    }
    document["functions"] = {
        "contextual": {
            "kind": "vectorize",
            "returns": "dataframe",
            "entrypoint": "unused:callable",
            "validate_signature": False,
        }
    }
    parsed = model.Spec.model_validate(document)
    key = ("pump_telemetry", "contextual")
    assert (
        parsed.get_row_context_resolution(key, "measurement_time")
        is parsed.dimensions["measurement_time"].resolutions[resolution_id]
    )
    assert parsed.get_row_context_resolution(key, "not_selected") is None

    if expected_error is None:
        row_context_rules.validate_dimension_type(parsed)
    else:
        with pytest.raises(ValueError, match=expected_error):
            row_context_rules.validate_dimension_type(parsed)
