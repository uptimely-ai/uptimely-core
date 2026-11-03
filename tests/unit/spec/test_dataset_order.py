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
    {"dimension": "$dimensions.machine", "direction": "asc"},
    {"dimension": "$dimensions.timestamp", "direction": "desc"},
]


def _configuration() -> dict[str, typing.Any]:
    return {
        "spec_version": 4,
        "dimensions": {
            "machine": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "external": {"type": "string"},
        },
        "functions": {},
        "profiles": {
            "observations": {
                "name": "Observations",
                "dimensions": ["machine", "timestamp"],
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
        ["$dimensions.machine"],
        [{"dimension": "$dimensions.machine"}],
        [{"direction": "asc"}],
        [{"dimension": "$dimensions.machine", "direction": "ASC"}],
        [{"dimension": "$dimensions.machine", "direction": "descending"}],
        [{"dimension": "$dimensions.machine", "direction": None}],
        [{"dimension": "machine", "direction": "asc"}],
        [{"dimension": "$features.machine", "direction": "asc"}],
        [{"dimension": "$dimensions.", "direction": "asc"}],
        [{"dimension": 1, "direction": "asc"}],
        [{"dimension": "$dimensions.machine", "direction": "asc", "nulls": "first"}],
    ],
)
def test_dataset_order_rejects_invalid_structure(tmp_path: pathlib.Path, order: object) -> None:
    with pytest.raises(pydantic.ValidationError):
        _parse(tmp_path, order)


@pytest.mark.parametrize("identifier", ["missing", "external", "@"])
def test_dataset_order_requires_declared_profile_dimensions(
    tmp_path: pathlib.Path, identifier: str
) -> None:
    with pytest.raises(validation.SpecError) as error:
        _parse(tmp_path, [{"dimension": f"$dimensions.{identifier}", "direction": "asc"}])

    assert error.value.code == "invalid_order_dimension"
    assert error.value.path == (
        "profiles",
        "observations",
        "order",
        0,
        "dimension",
    )


@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_dataset_order_rejects_repeated_dimensions(tmp_path: pathlib.Path, direction: str) -> None:
    with pytest.raises(validation.SpecError) as error:
        _parse(tmp_path, [ORDER[0], {"dimension": "$dimensions.machine", "direction": direction}])

    assert error.value.code == "duplicate_order_dimension"
    assert error.value.path[-3:] == ("order", 1, "dimension")


def test_dataset_order_reports_first_invalid_key_in_sequence(tmp_path: pathlib.Path) -> None:
    order = [
        ORDER[0],
        {"dimension": "$dimensions.machine", "direction": "desc"},
        {"dimension": "$dimensions.external", "direction": "asc"},
    ]

    with pytest.raises(validation.SpecError) as error:
        _parse(tmp_path, order)

    assert error.value.code == "duplicate_order_dimension"
    assert error.value.path[-3:] == ("order", 1, "dimension")


def test_dataset_order_python_authoring_matches_json(tmp_path: pathlib.Path) -> None:
    declaration = python_spec.profile.Profile(
        id="observations",
        order=[
            python_spec.profile.Order(
                dimension=python_spec.ref.dimension("machine"), direction="asc"
            ),
            python_spec.profile.Order(dimension="$dimensions.timestamp", direction="desc"),
        ],
    )
    dimensions = [
        python_spec.dimension.Dimension(id="machine", type="string"),
        python_spec.dimension.Dimension(id="timestamp", type="datetime"),
    ]
    declaration.dimensions = [item.id for item in dimensions]
    spec_definition = spec.from_python(
        profiles=[declaration], dimensions=dimensions, name="telemetry"
    )
    assert spec_definition.profiles["observations"].order == (
        _parse(tmp_path, ORDER).profiles["observations"].order
    )
    path = tmp_path / "python.json"
    spec.write_document(spec_definition, path)
    assert spec.load_spec(path).profiles["observations"].order == [
        spec.Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    with pytest.raises(pydantic.ValidationError):
        python_spec.profile.Order(
            dimension=python_spec.ref.feature("machine"), direction="asc"
        ).to_model()

    with pytest.raises(validation.SpecError, match="undeclared dimension"):
        spec.from_python(
            profiles=[
                python_spec.profile.Profile(
                    id="observations",
                    order=[
                        python_spec.profile.Order(
                            dimension=python_spec.ref.dimension("missing"),
                            direction="asc",
                        )
                    ],
                )
            ]
        )


def test_dataset_order_does_not_change_plan_or_sort_engine_rows(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    identifier = python_spec.dimension.Dimension(id="id", type="integer")
    declaration = python_spec.profile.Profile(
        id="ordered_values",
        producers=[
            python_spec.actions.Action(
                id="read",
                inputs=[],
                function=python_spec.ref.function(_read_order_data, kind="read"),
                arguments={},
                outputs=[
                    python_spec.feature.Feature(id="input_1"),
                    python_spec.feature.Feature(id="input_2"),
                    python_spec.feature.Feature(id="id", type="integer"),
                ],
            ),
            python_spec.actions.Action(
                id="sum",
                inputs=[python_spec.ref.feature("input_1"), python_spec.ref.feature("input_2")],
                function=python_spec.ref.function(_sum_order_features, kind="vectorize"),
                arguments={
                    "left_feature": python_spec.ref.feature("input_1"),
                    "right_feature": python_spec.ref.feature("input_2"),
                    "output": "sum",
                    "dataset": python_spec.ref.current_dataset().dataframe,
                },
                outputs=[python_spec.feature.Feature(id="sum")],
            ),
        ],
    )
    declaration.dimensions = [identifier]
    unordered = spec.from_python(profiles=[declaration], dimensions=[identifier])
    ordered = spec.from_python(
        profiles=[
            python_spec.profile.Profile(
                id=declaration.id,
                producers=declaration.producers,
                dimensions=[identifier],
                order=[
                    python_spec.profile.Order(
                        dimension=python_spec.ref.dimension("id"), direction="desc"
                    )
                ],
            )
        ],
        dimensions=[identifier],
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
