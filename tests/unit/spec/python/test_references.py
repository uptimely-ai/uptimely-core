import logging

import pytest

from uptimely.spec.python import assembly, conversion, dimension, feature, merge, profile, ref


def test_profile_identifiers_include_only_selected_grain_resolutions() -> None:
    machines = dimension.Dimension(
        id="machines",
        resolutions=[
            dimension.Resolution(id="pump", key="pump_id", type="string", parent="series"),
            dimension.Resolution(id="series", key="series_id", type="string"),
            dimension.Resolution(id="sensor", key="sensor_id", type="integer", parent="pump"),
        ],
    )
    sites = dimension.Dimension(
        id="sites",
        resolutions=[dimension.Resolution(id="site", key="site_id", type="string")],
    )
    declaration = profile.Profile(
        id="pumps", grain=[machines.resolution("series"), sites.resolution("site")]
    )
    dimensions = {item.id: item.to_model() for item in (machines, sites)}
    canonical = declaration.to_model()

    assert declaration.keys == ["series_id", "site_id"]
    assert declaration.identifiers == ["series_id", "site_id"]
    assert declaration.key_types == {
        "series_id": "string",
        "site_id": "string",
    }
    assert declaration.keys == canonical.keys(dimensions)
    assert declaration.key_types == canonical.key_types(dimensions)
    assert declaration.identifier_types == canonical.identifier_types(dimensions)
    assert [item.key for item in declaration.grain] == ["series_id", "site_id"]
    assert profile.Profile(id="global").keys == []
    assert profile.Profile(id="global").key_types == {}


def test_profile_identifier_properties_reject_unowned_resolutions() -> None:
    declaration = profile.Profile(
        id="invalid", grain=[dimension.Resolution(id="pump", key="pump_id", type="string")]
    )

    with pytest.raises(ValueError, match="Dimension.resolution"):
        _ = declaration.keys
    with pytest.raises(ValueError, match="Dimension.resolution"):
        _ = declaration.key_types


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_output_reference_logging_is_one_counted_summary(
    caplog: pytest.LogCaptureFixture, level: int
) -> None:
    caplog.set_level(level, logger="uptimely.spec.python")
    declarations = [
        profile.Profile(
            id=f"dataset_{index}",
            assembly=[
                assembly.Operator(
                    id=f"read_{operator}",
                    outputs=[feature.Feature(id=f"value_{operator}")],
                    compute=assembly.Bind(
                        ref.function("reader:read", returns="dataframe"),
                        column=ref.feature(f"value_{operator}"),
                    ),
                )
                for operator in range(count)
            ],
        )
        for index, count in enumerate([2, 1])
    ]

    conversion.to_model(profiles=tuple(declarations))

    assert caplog.messages == (
        ["Collected feature interfaces for 3 operators"] if level == logging.DEBUG else []
    )


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("staged", [False, True])
def test_foreign_feature_inputs_are_independent_of_merge(explicit: bool, staged: bool) -> None:
    source = profile.Profile(
        id="source",
        assembly=[
            assembly.Operator(
                outputs=[feature.Feature(id="value")],
                compute=assembly.Bind(ref.function("reader:read", returns="dataframe")),
            )
        ],
    )
    binding = assembly.Bind(
        ref.function("reader:copy", returns="dataframe"),
        value=ref.feature("value"),
    )
    target = profile.Profile(
        id="target",
        assembly=[
            assembly.Operator(
                inputs=["value"] if explicit else None,
                outputs=[feature.Feature(id="copied")],
                compute=binding,
                merge=merge.default() if staged else None,
            )
        ],
    )
    document = conversion.to_model([source, target])
    operator = next(iter(document.profiles["target"].assembly.values()))
    assert operator.compute.function == "copy"
    assert (operator.merge is not None) == staged
    assert operator.input_features == ["value"]


def test_compute_preserves_mixed_logical_profile_inputs() -> None:
    source = profile.Profile(
        id="source",
        assembly=[
            assembly.Operator(
                outputs=[feature.Feature(id="foreign")],
                compute=assembly.Bind(ref.function("reader:foreign", returns="dataframe")),
            )
        ],
    )
    local = assembly.Operator(
        outputs=[feature.Feature(id="local")],
        compute=assembly.Bind(ref.function("reader:local", returns="dataframe")),
    )
    binding = assembly.Bind(ref.function("reader:calculate", returns="dataframe"))
    calculation = assembly.Operator(
        inputs=["local"],
        outputs=[feature.Feature(id="result")],
        compute=binding,
    )
    target = profile.Profile(id="target", assembly=[local, calculation])
    document = conversion.to_model([source, target])
    assert document.profiles["target"].assembly[calculation.id].input_features == ["local"]

    calculation.inputs.append("foreign")
    document = conversion.to_model([source, target])
    assert document.profiles["target"].assembly[calculation.id].input_features == [
        "local",
        "foreign",
    ]
