import dataclasses
from collections import abc

import pytest

from uptimely.spec.python import Spec, assembly, conversion, dimension, feature, merge, profile, ref


def _source(
    columns: list[str] | None = None,
    path: str | int | None = None,
    dataset: object = None,
    other_dataset: object = None,
) -> object:
    pass


def _other_source(
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


def _expansion_source() -> profile.Profile:
    return profile.Profile(
        id="shared_source",
        assembly=[
            assembly.Operator(
                id="_other_source",
                inputs=[],
                outputs=[feature.Feature(id="temperature")],
                compute=assembly.Bind(
                    ref.function(_other_source, returns="dataframe"),
                ),
            )
        ],
    )


def _conform_source(identifier: str) -> profile.Profile:
    return profile.Profile(
        id=f"{identifier}_source",
        assembly=[
            assembly.Operator(
                id="_other_source",
                inputs=[],
                outputs=[feature.Feature(id="temperature")],
                compute=assembly.Bind(
                    ref.function(_other_source, returns="dataframe"),
                ),
            )
        ],
    )


def test_function_catalog_keeps_distinct_contracts_without_operator_labels() -> None:
    additional = profile.Profile(
        id="additional",
        assembly=[
            assembly.Operator(
                id="_other_source",
                inputs=[],
                outputs=[],
                compute=assembly.Bind(
                    ref.function(_other_source, returns="dataframe"),
                ),
            )
        ],
    )
    spec_definition = _python_spec(
        [
            _declaration("first", "read"),
            additional,
            _declaration("calculated", "transform"),
        ]
    )

    catalog = spec_definition.function_catalog()

    assert set(catalog) == {"read_shared", "_other_source", "transform_shared"}
    assert catalog["_other_source"].entrypoint == f"{__name__}:_other_source"
    assert catalog["read_shared"].returns == "dataframe"
    assert catalog["transform_shared"].returns == "dataframe"


@pytest.mark.parametrize("scenario", ["read", "write", "transform", "expand", "conform"])
def test_function_catalog_merges_and_deduplicates_contracts(scenario: str) -> None:
    first = _declaration("first", scenario)
    second = _declaration("second", scenario)
    profiles = [first, second]
    if scenario == "conform":
        profiles.append(_conform_source("first"))
        profiles.append(_conform_source("second"))
    if scenario == "expand":
        profiles.insert(0, _expansion_source())
    spec_definition = _python_spec(profiles)

    catalog = spec_definition.function_catalog()

    function_id = f"{scenario}_shared"
    assert catalog[function_id] == first.function_catalog()[function_id]
    assert catalog[function_id].entrypoint == f"{__name__}:{function_id}"
    expected_dataframe_inputs = {
        "read": 0,
        "write": 1,
        "transform": 1,
        "expand": 1,
        "conform": 1,
    }[scenario]
    assert sum(arg.type == "dataframe" for arg in catalog[function_id].args.values()) == (
        expected_dataframe_inputs
    )
    assert catalog[function_id].args["columns"].type == "array[string]"
    payload = spec_definition.to_dict()
    assert payload["functions"][function_id] == {
        "name": scenario.title() + " Shared",
        "description": None,
        "category": None,
        "returns": "none" if scenario == "write" else "dataframe",
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
            if scenario == "expand"
            else "first_source"
            if scenario == "conform"
            else "@"
        )
        expected_args["dataset"] = f"$profiles.{source_id}.dataset"
    assert payload["profiles"]["first"]["assembly"]["first_mapping"]["compute"] == {
        "function": function_id,
        "args": expected_args,
    }


@pytest.mark.parametrize("scenario", ["read", "write", "transform", "expand", "conform"])
def test_function_catalog_rejects_conflicting_entrypoints(scenario: str) -> None:
    profiles = [
        _declaration("first", scenario),
        _declaration("second", scenario, _other_source),
    ]
    if scenario == "conform":
        profiles.extend([_conform_source("first"), _conform_source("second")])
    if scenario == "expand":
        profiles.insert(0, _expansion_source())
    spec_definition = _python_spec(profiles)

    with pytest.raises(
        ValueError, match=f"Conflicting function definition for '{scenario}_shared'"
    ):
        spec_definition.to_dict()


def test_catalog_conflicts_are_rejected_consistently() -> None:
    first = profile.Profile(
        id="first",
        assembly=[
            assembly.Operator(
                id="_source",
                inputs=[],
                outputs=[],
                compute=assembly.Bind(
                    ref.function(_source, returns="dataframe"),
                    path="readings.json",
                ),
            )
        ],
    )
    second = profile.Profile(
        id="second",
        assembly=[
            assembly.Operator(
                id="_source",
                inputs=[],
                outputs=[],
                compute=assembly.Bind(
                    ref.function(_source, returns="dataframe"),
                    path=42,
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
        grain = [pump.resolution("machine")]
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
    assert payload["spec_version"] == 9
    assert "options" not in payload
    assert payload["source"] == {"name": "python_api", "generated": True}
    assert payload["dimensions"] == {
        "machine": {
            "resolutions": {
                "machine": {
                    "key": "pump",
                    "type": "string",
                    "parent": None,
                    "name": None,
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
            "relations": [],
            "scope": "One row per pump observation",
            "seed": None,
            "order": [{"dimension": "machine", "resolution": "machine", "direction": "desc"}],
            "features": {},
            "assembly": {},
        }
    }
