from collections import abc

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec.python import Spec, assembly, dimension, merge, profile, ref


def _source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> object:
    pass


def _declaration(
    identifier: str, scenario: str, function: abc.Callable[..., object] = _source
) -> profile.Profile:
    is_expand = scenario == "expand"
    is_dimensional = scenario in {"conform", "expand"}
    module = __name__ if function is _source else f"{__name__}.alternate"
    binding = assembly.Bind(
        ref.FunctionReference(
            module=module,
            name=f"{scenario}_shared",
            returns="none" if scenario == "write" else "dataframe",
        ),
        **{
            **({"dataset": ref.profile().dataset} if scenario in {"write", "transform"} else {}),
            **(
                {
                    "dataset": ref.profile(
                        "shared_source" if is_expand else f"{identifier}_source"
                    ).dataset,
                }
                if is_dimensional
                else {}
            ),
            "columns": [ref.input("temperature")],
        },
    )
    declarations = [
        assembly.Operator(
            id=f"{identifier}_mapping",
            inputs=[ref.input("temperature")] if is_dimensional else [],
            outputs=[],
            compute=binding,
            merge=merge.default() if is_dimensional else None,
        )
    ]
    return profile.Profile(
        id=identifier,
        assembly=declarations,
    )


def _python_spec(profiles: list[profile.Profile], name: str | None = None) -> Spec:
    return Spec(profiles=profiles, name=name)


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
        grain = [pump.at("machine")]

    class Summary(profile.Profile):
        id = "summary"
        grain = [pump.at("machine")]

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
    readings.grain = [pump.at("machine")]
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
    assert "pump" not in canonical.features
    assert canonical.assembly["readings_mapping"].interface.outputs == []
    assert readings.grain == [pump.at("machine")]


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
    with pytest.raises(ValueError, match="does not declare resolution 'fleet'"):
        machine.at("fleet")


def test_python_spec_rejects_duplicate_profiles_and_conflicting_metadata() -> None:
    pump = dimension.Dimension(
        id="pump",
        resolutions=[dimension.Resolution(id="machine", key="pump", type="string")],
    )
    readings = profile.Profile(id="readings", grain=[pump.at("machine")])
    with pytest.raises(ValueError, match="Duplicate profile id readings"):
        Spec(profiles=[readings, readings]).to_model()
    with pytest.raises(ValueError, match="Conflicting metadata for dimension 'pump'"):
        Spec(
            profiles=[
                readings,
                profile.Profile(
                    id="summary",
                    grain=[
                        dimension.Dimension(
                            id="pump",
                            resolutions=[
                                dimension.Resolution(id="machine", key="pump_id", type="integer")
                            ],
                        ).at("machine"),
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
        grain=[timestamp.at("timestamp"), pump.at("machine")],
    )
    definition = Spec(profiles=[readings])

    assert definition.to_dict()["profiles"]["readings"]["grain"] == [
        {"dimension": "timestamp", "resolution": "timestamp"},
        {"dimension": "machine", "resolution": "machine"},
    ]
    assert list(definition.to_model().dimensions) == ["timestamp", "machine"]
