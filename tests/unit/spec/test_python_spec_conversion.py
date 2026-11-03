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
            producers=[
                actions.Action(
                    id=f"read_{action}",
                    function=ref.function("reader:read", kind="read"),
                    arguments={"column": ref.output(f"value_{action}")},
                    outputs=[feature.Feature(id=f"value_{action}")],
                )
                for action in range(count)
            ],
        )
        for index, count in enumerate([2, 1])
    ]

    conversion.to_model(profiles=iter(declarations))

    assert caplog.messages == (
        ["\nPython spec validation:\n  - checked output references for 3 actions"]
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
    declarations = [
        actions.Action(
            id=f"{identifier}_mapping",
            inputs=[ref.feature("temperature")] if is_dimensional else [],
            function=ref.function(function, kind=category),
            arguments={
                **(
                    {"dataset": ref.current_dataset().dataframe}
                    if category in {"write", "vectorize", "collapse"}
                    else {}
                ),
                **(
                    {
                        "dataset": ref.dataset(
                            "shared_source" if is_expand else f"{identifier}_source"
                        ).dataframe,
                    }
                    if is_dimensional
                    else {}
                ),
                "columns": [ref.feature("temperature")],
            },
            outputs=[],
            function_id=f"{category}_shared",
        )
    ]
    return profile.Profile(
        id=identifier,
        producers=declarations if category not in {"write", "escape"} else [],
        publishers=declarations if category == "write" else [],
        pipelines=declarations if category == "escape" else [],
    )


def _python_spec(profiles: list[profile.Profile], name: str | None = None) -> Spec:
    dimensions = {
        item.id: item
        for declaration in profiles
        for item in declaration.dimensions
        if isinstance(item, dimension.Dimension)
    }
    return Spec(
        profiles=profiles,
        dimensions=list(dimensions.values()),
        name=name,
    )


def _mapping_source(dimensions: list[dimension.Dimension]) -> profile.Profile:
    return profile.Profile(
        id="shared_source",
        dimensions=dimensions,
        producers=[
            actions.Action(
                id="_other_source",
                inputs=[],
                function=ref.function(_other_source, kind="read"),
                arguments={},
                outputs=[feature.Feature(id="temperature")],
            )
        ],
    )


def _conform_source(identifier: str) -> profile.Profile:
    return profile.Profile(
        id=f"{identifier}_source",
        producers=[
            actions.Action(
                id="_other_source",
                inputs=[],
                function=ref.function(_other_source, kind="read"),
                arguments={},
                outputs=[feature.Feature(id="temperature")],
            )
        ],
    )


def test_empty_spec_has_no_profiles_or_functions() -> None:
    spec_definition = Spec(profiles=[], dimensions=[])

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


def test_python_spec_accepts_profile_classes_with_profile_dimensions() -> None:
    pump = dimension.Dimension(id="pump", type="string")

    class Readings(profile.Profile):
        id = "readings"
        dimensions = [pump]

    class Summary(profile.Profile):
        id = "summary"
        dimensions = [pump]

    spec_definition = Spec(profiles=[Readings, Summary], dimensions=[pump])

    assert [item.id for item in spec_definition.profiles] == ["readings", "summary"]
    assert [item.id for item in spec_definition.to_model().profiles["readings"].dimensions] == [
        "pump"
    ]


@pytest.mark.parametrize("dimension_id", [False, True])
def test_python_spec_resolves_registered_ids_and_objects_without_mutation(
    dimension_id: bool,
) -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Pump identifier")
    readings = _declaration("readings", "read")
    readings.dimensions = ["pump" if dimension_id else pump]
    definition = Spec(profiles=[readings], dimensions=[pump])

    document = definition.to_model()
    payload = definition.to_dict()

    assert document.profiles["readings"].dimensions[0].id == "pump"
    assert payload["profiles"]["readings"]["dimensions"] == ["pump"]
    assert payload["dimensions"]["pump"]["description"] == "Pump identifier"
    canonical = document.profiles["readings"]
    assert canonical.features["pump"].type == "string"
    assert canonical.actions["readings_mapping"].features.outputs == ["$features.pump"]
    assert readings.dimensions == (["pump"] if dimension_id else [pump])


def test_dimension_name_defaults_to_humanized_id_and_can_be_overridden() -> None:
    default_dimension = dimension.Dimension(id="production_line", type="string")
    named_dimension = dimension.Dimension(
        id="production_line", type="string", name="Production Line Name"
    )

    assert default_dimension.name == "Production Line"
    assert default_dimension.to_model().name == "Production Line"
    assert named_dimension.to_model().name == "Production Line Name"


def test_python_spec_requires_a_profile_registry() -> None:
    with pytest.raises(TypeError, match="profiles"):
        Spec()


@pytest.mark.parametrize("object_reference", [False, True])
def test_python_spec_rejects_undeclared_references(object_reference: bool) -> None:
    pump = dimension.Dimension(id="pump", type="string")
    readings = profile.Profile(id="readings", dimensions=[pump if object_reference else "pump"])
    with pytest.raises(ValueError, match="undeclared dimension 'pump'"):
        Spec(dimensions=[], profiles=[readings]).to_model()


def test_python_spec_rejects_duplicate_registrations_and_conflicting_metadata() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    readings = profile.Profile(id="readings", dimensions=[pump])
    with pytest.raises(ValueError, match="Duplicate dimension id pump"):
        Spec(dimensions=[pump, pump], profiles=[readings]).to_model()
    with pytest.raises(ValueError, match="Duplicate profile id readings"):
        Spec(dimensions=[pump], profiles=[readings, readings]).to_model()
    with pytest.raises(ValueError, match="Conflicting metadata for dimension 'pump'"):
        Spec(
            dimensions=[dimension.Dimension(id="pump", type="integer")],
            profiles=[readings],
        ).to_model()


def test_python_spec_preserves_unused_registrations_without_inferring_profiles() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    readings = profile.Profile(id="readings")
    definition = Spec(dimensions=[pump], profiles=[readings])

    payload = definition.to_dict()

    assert list(payload["dimensions"]) == ["pump"]
    assert payload["profiles"]["readings"]["dimensions"] == []
    assert [item.id for item in definition.profiles] == ["readings"]


def test_python_spec_resolves_mixed_dimension_references_in_declared_order() -> None:
    pump = dimension.Dimension(id="pump", type="string")
    timestamp = dimension.Dimension(id="timestamp", type="datetime")
    readings = profile.Profile(id="readings", dimensions=["timestamp", pump])
    definition = Spec(dimensions=[pump, timestamp], profiles=[readings])

    assert definition.to_dict()["profiles"]["readings"]["dimensions"] == [
        "timestamp",
        "pump",
    ]
    assert [item.id for item in definition.dimensions] == ["pump", "timestamp"]


def test_function_catalog_keeps_distinct_functions_and_kinds() -> None:
    additional = profile.Profile(
        id="additional",
        producers=[
            actions.Action(
                id="_other_source",
                inputs=[],
                function=ref.function(_other_source, kind="read"),
                arguments={},
                outputs=[],
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
        profiles.insert(0, _mapping_source([]))
    spec_definition = _python_spec(profiles)

    catalog = spec_definition.function_catalog()

    function_id = f"{category}_shared"
    assert catalog[function_id] == first.function_catalog()[function_id]
    assert catalog[function_id].entrypoint == f"{__name__}:_source"
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
        "entrypoint": f"{__name__}:_source",
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
        expected_args["dataset"] = f"$datasets.{source_id}.dataframe"
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
        profiles.insert(0, _mapping_source([]))
    spec_definition = _python_spec(profiles)

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{category}_shared'"
    ):
        spec_definition.to_dict()


def test_catalog_conflicts_are_rejected_consistently() -> None:
    first = profile.Profile(
        id="first",
        producers=[
            actions.Action(
                id="_source",
                inputs=[],
                function=ref.function(_source, kind="read"),
                arguments={"path": "readings.json"},
                outputs=[],
                function_id="shared",
            )
        ],
    )
    second = profile.Profile(
        id="second",
        producers=[
            actions.Action(
                id="_source",
                inputs=[],
                function=ref.function(_source, kind="read"),
                arguments={"path": 42},
                outputs=[],
                function_id="shared",
            )
        ],
    )
    spec_definition = _python_spec([first, second])

    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        spec_definition.function_catalog()
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        conversion.to_dict(profiles=[first, second])

    combined = profile.Profile(
        id="combined",
        producers=[
            dataclasses.replace(first.producers[0], id="first"),
            dataclasses.replace(second.producers[0], id="second"),
        ],
    )
    with pytest.raises(ValueError, match="Conflicting function definition for 'shared'"):
        combined.function_catalog()


def test_to_dict_preserves_name_dimensions_and_profile_metadata() -> None:
    pump = dimension.Dimension(id="pump", type="string", description="Asset ID")

    class Telemetry(profile.Profile):
        id = "telemetry"
        name = "Pump Telemetry"
        description = "Telemetry readings"
        dimensions = [pump]
        category = "telemetry"
        order = [profile.Order(dimension=ref.dimension("pump"), direction="desc")]

    spec_definition = Spec(
        dimensions=[pump],
        profiles=[Telemetry],
        name="Pump analytics",
    )

    payload = spec_definition.to_dict()

    assert dimension.Dimension(id="pump", type="string").name == "Pump"
    assert pump.to_model().name == "Pump"
    assert payload["name"] == "Pump analytics"
    assert payload["spec_version"] == 4
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "pump": {
            "type": "string",
            "name": "Pump",
            "description": "Asset ID",
            "parent": None,
        }
    }
    assert payload["profiles"] == {
        "telemetry": {
            "name": "Pump Telemetry",
            "description": "Telemetry readings",
            "category": "telemetry",
            "dimensions": ["pump"],
            "row_scope": {"grain": "", "filtering": "", "coverage": ""},
            "order": [{"dimension": "$dimensions.pump", "direction": "desc"}],
            "features": {},
            "actions": {},
        }
    }
