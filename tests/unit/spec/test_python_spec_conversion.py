import dataclasses
import logging
from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import (
    Spec,
    actions,
    conversion,
    dimension,
    feature,
    profile,
    ref,
)


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_output_reference_logging_is_one_counted_summary(
    caplog: pytest.LogCaptureFixture, level: int
) -> None:
    caplog.set_level(level, logger="uptimely.spec.python")
    declarations = [
        profile.Profile(
            id=f"dataset_{index}",
            assembly=[
                actions.Operator(
                    id=f"read_{action}",
                    interface=actions.Interface(
                        outputs=[feature.Feature(id=f"value_{action}")],
                    ),
                    compute=actions.Binding(
                        function=ref.function("reader:read", kind="read"),
                        arguments={"column": ref.feature(f"value_{action}")},
                    ),
                )
                for action in range(count)
            ],
        )
        for index, count in enumerate([2, 1])
    ]

    conversion.to_model(profiles=iter(declarations))

    assert caplog.messages == (
        ["\nPython spec validation:\n  - collected feature interfaces for 3 actions"]
        if level == logging.DEBUG
        else []
    )


def _source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> None:
    pass


def _other_source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> None:
    pass


def _declaration(
    identifier: str, category: str, function: abc.Callable[..., object] = _source
) -> profile.Profile:
    is_expand = category == "expand"
    is_dimensional = category in {"conform", "expand"}
    module = __name__ if function is _source else f"{__name__}.alternate"
    declarations = [
        actions.Operator(
            id=f"{identifier}_mapping",
            interface=actions.Interface(
                inputs=[ref.feature("temperature")] if is_dimensional else [],
                outputs=[],
            ),
            compute=actions.Binding(
                function=ref.FunctionReference(
                    module=module,
                    name=f"{category}_shared",
                    kind=category,
                ),
                arguments={
                    **(
                        {"dataset": ref.profile().data}
                        if category in {"write", "vectorize", "collapse"}
                        else {}
                    ),
                    **(
                        {
                            "dataset": ref.profile(
                                "shared_source" if is_expand else f"{identifier}_source"
                            ).data,
                        }
                        if is_dimensional
                        else {}
                    ),
                    "columns": [ref.feature("temperature")],
                },
            ),
        )
    ]
    return profile.Profile(
        id=identifier,
        assembly=declarations,
    )


def _python_spec(profiles: list[profile.Profile], name: str | None = None) -> Spec:
    return Spec(profiles=profiles, name=name)


def _mapping_source() -> profile.Profile:
    return profile.Profile(
        id="shared_source",
        assembly=[
            actions.Operator(
                id="_other_source",
                interface=actions.Interface(
                    inputs=[],
                    outputs=[feature.Feature(id="temperature")],
                ),
                compute=actions.Binding(
                    function=ref.function(_other_source, kind="read"),
                    arguments={},
                ),
            )
        ],
    )


def _conform_source(identifier: str) -> profile.Profile:
    return profile.Profile(
        id=f"{identifier}_source",
        assembly=[
            actions.Operator(
                id="_other_source",
                interface=actions.Interface(
                    inputs=[],
                    outputs=[feature.Feature(id="temperature")],
                ),
                compute=actions.Binding(
                    function=ref.function(_other_source, kind="read"),
                    arguments={},
                ),
            )
        ],
    )


def test_empty_spec_has_no_profiles_or_functions() -> None:
    spec_definition = Spec(profiles=[])

    assert spec_definition.profiles == ()
    assert spec_definition.function_catalog() == spec_model.FunctionCatalog()
    with pytest.raises(ValueError, match="At least one profile is required"):
        spec_definition.to_dict()


def test_python_spec_requires_a_sequence_of_profiles() -> None:
    with pytest.raises(TypeError, match="profiles must be a sequence"):
        tuple(Spec(profiles={}).profiles)
    assert Spec(profiles=[profile.Profile(id="readings")]).profiles[0].id == "readings"


def test_profile_registry_preserves_registration_order() -> None:
    first = profile.Profile(id="first")
    second = profile.Profile(id="second")
    third = profile.Profile(id="third")
    spec_definition = _python_spec([first, second, third])

    assert list(spec_definition.profiles) == [first, second, third]


def test_python_spec_accepts_profile_classes_with_profile_grain() -> None:
    pump = dimension.Dimension(
        id="pump",
        resolutions=[dimension.Resolution(id="machine", key="pump_id", type="string")],
    )

    class Readings(profile.Profile):
        id = "readings"
        grain = [profile.Grain(pump, "machine")]

    class Summary(profile.Profile):
        id = "summary"
        grain = [profile.Grain(pump, "machine")]

    spec_definition = Spec(profiles=[Readings, Summary])

    assert [item.id for item in spec_definition.profiles] == ["readings", "summary"]
    assert spec_definition.to_model().profiles["readings"].grain[0].dimension == "pump"
    assert list(spec_definition.to_model().dimensions["pump"].resolutions) == ["machine"]


def test_python_spec_infers_selected_key_and_available_resolutions() -> None:
    pump = dimension.Dimension(
        id="machine",
        description="Machine identifier",
        resolutions=[
            dimension.Resolution(id="machine", key="pump", type="string"),
            dimension.Resolution(id="fleet", key="fleet", type="string"),
        ],
    )
    readings = _declaration("readings", "read")
    readings.grain = [profile.Grain(pump, "machine")]
    definition = Spec(profiles=[readings])

    document = definition.to_model()
    payload = definition.to_dict()

    assert document.profiles["readings"].grain[0].resolution == "machine"
    assert payload["profiles"]["readings"]["grain"] == [
        {"dimension": "machine", "resolution": "machine"}
    ]
    assert payload["dimensions"]["machine"]["description"] == "Machine identifier"
    assert list(payload["dimensions"]["machine"]["resolutions"]) == ["machine", "fleet"]
    canonical = document.profiles["readings"]
    assert canonical.features["pump"].type == "string"
    assert canonical.actions["readings_mapping"].features.outputs == ["$features.pump"]
    assert readings.grain == [profile.Grain(pump, "machine")]


def test_dimension_name_defaults_to_humanized_id_and_can_be_overridden() -> None:
    default_dimension = dimension.Dimension(
        id="production_line",
        resolutions=[dimension.Resolution(id="line", key="production_line", type="string")],
    )
    named_dimension = dimension.Dimension(
        id="production_line",
        resolutions=[dimension.Resolution(id="line", key="production_line", type="string")],
        name="Production Line Name",
    )

    assert default_dimension.name == "Production Line"
    assert default_dimension.to_model().name == "Production Line"
    assert named_dimension.to_model().name == "Production Line Name"


def test_python_spec_requires_a_profile_registry() -> None:
    with pytest.raises(TypeError, match="profiles"):
        Spec()


def test_python_spec_rejects_unresolved_grain_resolutions() -> None:
    machine = dimension.Dimension(
        id="machine",
        resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
    )
    readings = profile.Profile(id="readings", grain=[profile.Grain(machine, "fleet")])
    with pytest.raises(ValueError, match="does not declare resolution 'fleet'"):
        Spec(profiles=[readings]).to_model()


def test_python_spec_rejects_duplicate_profiles_and_conflicting_metadata() -> None:
    pump = dimension.Dimension(
        id="pump",
        resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
    )
    readings = profile.Profile(id="readings", grain=[profile.Grain(pump, "machine")])
    with pytest.raises(ValueError, match="Duplicate profile id readings"):
        Spec(profiles=[readings, readings]).to_model()
    with pytest.raises(ValueError, match="Conflicting metadata for dimension 'pump'"):
        Spec(
            profiles=[
                readings,
                profile.Profile(
                    id="summary",
                    grain=[
                        profile.Grain(
                            dimension.Dimension(
                                id="pump",
                                resolutions=[
                                    dimension.Resolution(
                                        id="machine", key="pump_id", type="integer"
                                    )
                                ],
                            ),
                            "machine",
                        )
                    ],
                ),
            ],
        ).to_model()


def test_python_spec_infers_no_unused_dimension_registrations() -> None:
    readings = profile.Profile(id="readings")
    definition = Spec(profiles=[readings])

    payload = definition.to_dict()

    assert payload["dimensions"] == {}
    assert payload["profiles"]["readings"]["grain"] == []
    assert [item.id for item in definition.profiles] == ["readings"]


def test_python_spec_infers_dimensions_in_profile_grain_order() -> None:
    pump = dimension.Dimension(
        id="machine",
        resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
    )
    timestamp = dimension.Dimension(
        id="timestamp",
        resolutions=[dimension.Resolution(id="timestamp", key="timestamp", type="datetime")],
    )
    readings = profile.Profile(
        id="readings",
        grain=[profile.Grain(timestamp, "timestamp"), profile.Grain(pump, "machine")],
    )
    definition = Spec(profiles=[readings])

    assert definition.to_dict()["profiles"]["readings"]["grain"] == [
        {"dimension": "timestamp", "resolution": "timestamp"},
        {"dimension": "machine", "resolution": "machine"},
    ]
    assert list(definition.to_model().dimensions) == ["timestamp", "machine"]


def test_function_catalog_keeps_distinct_functions_and_kinds() -> None:
    additional = profile.Profile(
        id="additional",
        assembly=[
            actions.Operator(
                id="_other_source",
                interface=actions.Interface(
                    inputs=[],
                    outputs=[],
                ),
                compute=actions.Binding(
                    function=ref.function(_other_source, kind="read"),
                    arguments={},
                ),
            )
        ],
    )
    spec_definition = _python_spec(
        [
            _declaration("first", "read"),
            additional,
            _declaration("calculated", "vectorize"),
        ]
    )

    catalog = spec_definition.function_catalog()

    assert set(catalog.by_kind("read")) == {"read_shared", "_other_source"}
    assert catalog["_other_source"].entrypoint == f"{__name__}:_other_source"
    assert set(catalog.by_kind("vectorize")) == {"vectorize_shared"}
    assert all(not catalog.by_kind(kind) for kind in ("write", "collapse", "expand", "conform"))


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_merges_and_deduplicates_each_kind(category: str) -> None:
    first = _declaration("first", category)
    second = _declaration("second", category)
    profiles = [first, second]
    if category == "conform":
        profiles.append(_conform_source("first"))
        profiles.append(_conform_source("second"))
    if category == "expand":
        profiles.insert(0, _mapping_source())
    spec_definition = _python_spec(profiles)

    catalog = spec_definition.function_catalog()

    function_id = f"{category}_shared"
    assert catalog[function_id] == first.function_catalog()[function_id]
    assert catalog[function_id].entrypoint == f"{__name__}:{function_id}"
    expected_dataframe_inputs = {
        "read": 0,
        "write": 1,
        "vectorize": 1,
        "collapse": 1,
        "expand": 1,
        "conform": 1,
    }[category]
    assert sum(arg.type == "dataframe" for arg in catalog[function_id].args.values()) == (
        expected_dataframe_inputs
    )
    assert catalog[function_id].args["columns"].type == "array[string]"
    payload = spec_definition.to_dict()
    assert payload["functions"][function_id] == {
        "name": category.title() + " Shared",
        "description": None,
        "kind": category,
        "returns": "none" if category == "write" else "dataframe",
        "entrypoint": f"{__name__}:{function_id}",
        "validate_signature": True,
        "args": {
            "columns": {"type": "array[string]", "comment": None},
            **(
                {"dataset": {"type": "dataframe", "comment": None}}
                if expected_dataframe_inputs == 1
                else {}
            ),
        },
    }
    expected_args = {"columns": ["$features.temperature"]}
    if expected_dataframe_inputs:
        source_id = (
            "shared_source"
            if category == "expand"
            else "first_source"
            if category == "conform"
            else "@"
        )
        expected_args["dataset"] = f"$profiles.{source_id}.dataframe"
    assert payload["profiles"]["first"]["actions"]["first_mapping"]["binding"] == {
        "function": function_id,
        "args": expected_args,
    }


@pytest.mark.parametrize(
    "category", ["read", "write", "vectorize", "collapse", "expand", "conform"]
)
def test_function_catalog_rejects_conflicting_entrypoints(category: str) -> None:
    profiles = [
        _declaration("first", category),
        _declaration("second", category, _other_source),
    ]
    if category == "conform":
        profiles.extend([_conform_source("first"), _conform_source("second")])
    if category == "expand":
        profiles.insert(0, _mapping_source())
    spec_definition = _python_spec(profiles)

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{category}_shared'"
    ):
        spec_definition.to_dict()


def test_catalog_conflicts_are_rejected_consistently() -> None:
    first = profile.Profile(
        id="first",
        assembly=[
            actions.Operator(
                id="_source",
                interface=actions.Interface(
                    inputs=[],
                    outputs=[],
                ),
                compute=actions.Binding(
                    function=ref.function(_source, kind="read"),
                    arguments={"path": "readings.json"},
                ),
            )
        ],
    )
    second = profile.Profile(
        id="second",
        assembly=[
            actions.Operator(
                id="_source",
                interface=actions.Interface(
                    inputs=[],
                    outputs=[],
                ),
                compute=actions.Binding(
                    function=ref.function(_source, kind="read"),
                    arguments={"path": 42},
                ),
            )
        ],
    )
    spec_definition = _python_spec([first, second])

    with pytest.raises(ValueError, match="Conflicting function definition for '_source'"):
        spec_definition.function_catalog()
    with pytest.raises(ValueError, match="Conflicting function definition for '_source'"):
        conversion.to_dict(profiles=[first, second])

    combined = profile.Profile(
        id="combined",
        assembly=[
            dataclasses.replace(first.assembly[0], id="first"),
            dataclasses.replace(second.assembly[0], id="second"),
        ],
    )
    with pytest.raises(ValueError, match="Conflicting function definition for '_source'"):
        combined.function_catalog()


def test_to_dict_preserves_name_grain_and_profile_metadata() -> None:
    pump = dimension.Dimension(
        id="machine",
        description="Machine ID",
        resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
    )

    class Telemetry(profile.Profile):
        id = "telemetry"
        name = "Pump Telemetry"
        description = "Telemetry readings"
        grain = [profile.Grain(pump, "machine")]
        category = "telemetry"
        scope = "One row per pump observation"
        order = [profile.Order(pump, "machine", direction="desc")]

    spec_definition = Spec(
        profiles=[Telemetry],
        name="Pump analytics",
    )

    payload = spec_definition.to_dict()

    assert (
        dimension.Dimension(
            id="machine",
            resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
        ).name
        == "Machine"
    )
    assert pump.to_model().name == "Machine"
    assert payload["name"] == "Pump analytics"
    assert payload["spec_version"] == 4
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "machine": {
            "resolutions": {
                "machine": {
                    "key": "pump",
                    "type": "string",
                    "parent": None,
                }
            },
            "name": "Machine",
            "description": "Machine ID",
        }
    }
    assert payload["profiles"] == {
        "telemetry": {
            "name": "Pump Telemetry",
            "description": "Telemetry readings",
            "category": "telemetry",
            "grain": [{"dimension": "machine", "resolution": "machine"}],
            "scope": "One row per pump observation",
            "order": [{"dimension": "machine", "resolution": "machine", "direction": "desc"}],
            "features": {},
            "actions": {},
        }
    }
