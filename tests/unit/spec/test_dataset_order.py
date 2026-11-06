import json
import pathlib
import typing

import polars as pl
import pydantic
import pytest
from support import execution as execution_support

from uptimely import compiler, spec
from uptimely.spec import python as python_spec
from uptimely.spec import validation


def _read_order_data() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "input_1": [1, 3], "input_2": [2, 4]})


def _sum_order_features(
    dataset: pl.LazyFrame,
    left_feature: str,
    right_feature: str,
    output: str,
) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(left_feature) + pl.col(right_feature)).alias(output))


ORDER = [
    {"dimension": "machine", "resolution": "machine", "direction": "asc"},
    {"dimension": "timestamp", "resolution": "timestamp", "direction": "desc"},
]


def _configuration() -> dict[str, typing.Any]:
    return {
        "spec_version": 6,
        "dimensions": {
            "machine": {"resolutions": {"machine": {"key": "machine_id", "type": "string"}}},
            "timestamp": {"resolutions": {"timestamp": {"key": "timestamp", "type": "datetime"}}},
            "external": {"resolutions": {"external": {"key": "external_id", "type": "string"}}},
        },
        "functions": {},
        "profiles": {
            "observations": {
                "name": "Observations",
                "grain": [
                    {"dimension": "machine", "resolution": "machine"},
                    {"dimension": "timestamp", "resolution": "timestamp"},
                ],
                "order": ORDER,
            }
        },
    }


def _parse(tmp_path: pathlib.Path, order: object) -> spec.Spec:
    configuration = _configuration()
    configuration["profiles"]["observations"]["order"] = order
    path = tmp_path / "input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return spec.load_spec(path)


def test_dataset_order_json_round_trip_preserves_precedence(tmp_path: pathlib.Path) -> None:
    spec_definition = _parse(tmp_path, ORDER)
    keys = spec_definition.profiles["observations"].order
    assert keys == [spec.Order(**key) for key in ORDER]

    path = tmp_path / "export.json"
    spec.write_document(spec_definition, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["profiles"]["observations"]["order"] == ORDER
    assert spec.load_spec(path).profiles["observations"].order == keys


def test_dataset_order_defaults_to_empty_without_shared_state(tmp_path: pathlib.Path) -> None:
    assert _parse(tmp_path, []).profiles["observations"].order == []
    configuration = _configuration()
    del configuration["profiles"]["observations"]["order"]
    path = tmp_path / "omitted.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    assert spec.load_spec(path).profiles["observations"].order == []

    first = spec.Profile(id="first")
    second = spec.Profile(id="second")
    first.order.append(spec.Order(**ORDER[0]))
    assert second.order == []
    authored_first = python_spec.profile.Profile(id="first")
    authored_second = python_spec.profile.Profile(id="second")
    first_model = authored_first.to_model()
    first_model.order.append(spec.Order(**ORDER[0]))
    assert not authored_first.order
    assert not authored_second.order
    assert authored_second.to_model().order == []


@pytest.mark.parametrize(
    "order",
    [
        None,
        {},
        ["machine"],
        [{"dimension": "machine", "direction": "asc"}],
        [{"direction": "asc"}],
        [{"dimension": "machine", "resolution": "machine", "direction": "ASC"}],
        [{"dimension": "machine", "resolution": "machine", "direction": "descending"}],
        [{"dimension": "machine", "resolution": "machine", "direction": None}],
        [{"dimension": "machine", "resolution": "machine", "direction": "asc", "extra": True}],
        [
            {
                "dimension": "machine",
                "resolution": "machine",
                "direction": "asc",
                "nulls": "first",
            }
        ],
    ],
)
def test_dataset_order_rejects_invalid_structure(tmp_path: pathlib.Path, order: object) -> None:
    with pytest.raises(pydantic.ValidationError):
        _parse(tmp_path, order)


@pytest.mark.parametrize("identifier", ["missing", "external", "@"])
def test_dataset_order_requires_selected_profile_resolutions(
    tmp_path: pathlib.Path, identifier: str
) -> None:
    with pytest.raises(validation.SpecError) as error:
        _parse(
            tmp_path,
            [{"dimension": identifier, "resolution": "unknown", "direction": "asc"}],
        )

    assert error.value.code == "invalid_order_resolution"
    assert error.value.path == (
        "profiles",
        "observations",
        "order",
        0,
    )


@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_dataset_order_rejects_repeated_dimensions(tmp_path: pathlib.Path, direction: str) -> None:
    with pytest.raises(validation.SpecError) as error:
        _parse(
            tmp_path,
            [ORDER[0], {"dimension": "machine", "resolution": "machine", "direction": direction}],
        )

    assert error.value.code == "duplicate_order_resolution"
    assert error.value.path[-2:] == ("order", 1)


def test_dataset_order_reports_first_invalid_key_in_sequence(tmp_path: pathlib.Path) -> None:
    order = [
        ORDER[0],
        {"dimension": "machine", "resolution": "machine", "direction": "desc"},
        {"dimension": "external", "resolution": "external", "direction": "asc"},
    ]

    with pytest.raises(validation.SpecError) as error:
        _parse(tmp_path, order)

    assert error.value.code == "duplicate_order_resolution"
    assert error.value.path[-2:] == ("order", 1)


def test_dataset_order_python_authoring_matches_json(tmp_path: pathlib.Path) -> None:
    dimensions = [
        python_spec.dimension.Dimension(
            id="machine",
            resolutions=[
                python_spec.dimension.Resolution(id="machine", key="machine_id", type="string")
            ],
        ),
        python_spec.dimension.Dimension(
            id="timestamp",
            resolutions=[
                python_spec.dimension.Resolution(id="timestamp", key="timestamp", type="datetime")
            ],
        ),
    ]
    declaration = python_spec.profile.Profile(
        id="observations",
        grain=[
            python_spec.profile.Grain(dimensions[0], "machine"),
            python_spec.profile.Grain(dimensions[1], "timestamp"),
        ],
        order=[
            python_spec.profile.Order(dimensions[0], "machine", direction="asc"),
            python_spec.profile.Order(dimensions[1], "timestamp", direction="desc"),
        ],
    )
    spec_definition = spec.from_python(profiles=[declaration], name="telemetry")
    assert spec_definition.profiles["observations"].order == (
        _parse(tmp_path, ORDER).profiles["observations"].order
    )
    path = tmp_path / "python.json"
    spec.write_document(spec_definition, path)
    assert spec.load_spec(path).profiles["observations"].order == [
        spec.Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    machine = python_spec.dimension.Dimension(
        id="machine",
        resolutions=[
            python_spec.dimension.Resolution(id="machine", key="machine_id", type="string"),
            python_spec.dimension.Resolution(id="fleet", key="fleet_id", type="string"),
        ],
    )
    with pytest.raises(validation.SpecError, match="order references a resolution"):
        spec.from_python(
            profiles=[
                python_spec.profile.Profile(
                    id="observations",
                    grain=[python_spec.profile.Grain(machine, "machine")],
                    order=[python_spec.profile.Order(machine, "fleet", direction="asc")],
                )
            ]
        )


def test_dataset_order_does_not_change_plan_or_sort_engine_rows(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    identifier = python_spec.dimension.Dimension(
        id="id",
        resolutions=[python_spec.dimension.Resolution(id="id", key="id", type="integer")],
    )
    declaration = python_spec.profile.Profile(
        id="ordered_values",
        grain=[python_spec.profile.Grain(identifier, "id")],
        assembly=[
            python_spec.Operator(
                id="read",
                interface=python_spec.Interface(
                    inputs=[],
                    outputs=[
                        python_spec.feature.Feature(id="input_1"),
                        python_spec.feature.Feature(id="input_2"),
                        python_spec.feature.Feature(id="id", type="integer"),
                    ],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(_read_order_data, kind="read"),
                    arguments={},
                ),
            ),
            python_spec.Operator(
                id="sum",
                interface=python_spec.Interface(
                    inputs=[python_spec.ref.feature("input_1"), python_spec.ref.feature("input_2")],
                    outputs=[python_spec.feature.Feature(id="sum")],
                ),
                compute=python_spec.Binding(
                    function=python_spec.ref.function(_sum_order_features, kind="vectorize"),
                    arguments={
                        "left_feature": python_spec.ref.feature("input_1"),
                        "right_feature": python_spec.ref.feature("input_2"),
                        "output": "sum",
                        "dataset": python_spec.ref.profile().data,
                    },
                ),
            ),
        ],
    )
    unordered = spec.from_python(profiles=[declaration])
    ordered = spec.from_python(
        profiles=[
            python_spec.profile.Profile(
                id=declaration.id,
                assembly=declaration.assembly,
                grain=[python_spec.profile.Grain(identifier, "id")],
                order=[python_spec.profile.Order(identifier, "id", direction="desc")],
            )
        ]
    )
    assert (
        compiler.Compiler().compile(ordered).invocations
        == compiler.Compiler().compile(unordered).invocations
    )

    result = engine_for_plan(compiler.Compiler().compile(ordered), spec_definition=ordered).run()
    assert result.failures == {}
    frame = result.main_frames[declaration.id]
    assert isinstance(frame, pl.DataFrame)
    assert frame.select(_read_order_data().columns).rows() == _read_order_data().rows()
    assert frame["id"].to_list() != frame.sort("id", descending=True)["id"].to_list()
