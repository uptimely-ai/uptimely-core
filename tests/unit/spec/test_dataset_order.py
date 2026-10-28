import json
import pathlib
import typing

import polars as pl
import pydantic
import pytest
from conftest import engine_for_plan, render_explorer

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
        "spec_version": 2,
        "dimensions": {
            "machine": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "external": {"type": "string"},
        },
        "functions": {},
        "entities": {
            "telemetry": {
                "name": "Telemetry",
                "dimensions": ["machine", "timestamp"],
                "datasets": {"observations": {"order": ORDER}},
            }
        },
    }


def _parse(tmp_path: pathlib.Path, order: object) -> spec.Spec:
    configuration = _configuration()
    configuration["entities"]["telemetry"]["datasets"]["observations"]["order"] = order
    path = tmp_path / "input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return spec.load_spec(path)


def test_dataset_order_json_round_trip_preserves_precedence(tmp_path: pathlib.Path) -> None:
    spec_definition = _parse(tmp_path, ORDER)
    keys = spec_definition.entities["telemetry"].datasets["observations"].order
    assert keys == [spec.Order(**key) for key in ORDER]

    path = tmp_path / "export.json"
    spec.write_document(spec_definition, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entities"]["telemetry"]["datasets"]["observations"]["order"] == ORDER
    assert spec.load_spec(path).entities["telemetry"].datasets["observations"].order == keys


def test_dataset_order_defaults_to_empty_without_shared_state(tmp_path: pathlib.Path) -> None:
    assert _parse(tmp_path, []).entities["telemetry"].datasets["observations"].order == []
    configuration = _configuration()
    del configuration["entities"]["telemetry"]["datasets"]["observations"]["order"]
    path = tmp_path / "omitted.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    assert spec.load_spec(path).entities["telemetry"].datasets["observations"].order == []

    first = spec.Dataset(id="first")
    second = spec.Dataset(id="second")
    first.order.append(spec.Order(**ORDER[0]))
    assert second.order == []
    authored_first = python_spec.dataset.Dataset(id="first")
    authored_second = python_spec.dataset.Dataset(id="second")
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
def test_dataset_order_requires_owning_entity_dimensions(
    tmp_path: pathlib.Path, identifier: str
) -> None:
    with pytest.raises(validation.SpecError) as error:
        _parse(tmp_path, [{"dimension": f"$dimensions.{identifier}", "direction": "asc"}])

    assert error.value.code == "invalid_order_dimension"
    assert error.value.path == (
        "entities",
        "telemetry",
        "datasets",
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


@pytest.mark.parametrize("use_entities", [True, False])
def test_dataset_order_python_authoring_matches_json(
    tmp_path: pathlib.Path, use_entities: bool
) -> None:
    declaration = python_spec.dataset.Dataset(
        id="observations",
        order=[
            python_spec.dataset.Order(
                dimension=python_spec.ref.dimension("machine"), direction="asc"
            ),
            python_spec.dataset.Order(dimension="$dimensions.timestamp", direction="desc"),
        ],
    )
    dimensions = [
        python_spec.dimension.Dimension(id="machine", type="string"),
        python_spec.dimension.Dimension(id="timestamp", type="datetime"),
    ]
    if use_entities:
        spec_definition = spec.from_python(
            entities=[
                python_spec.entity.Entity(
                    id="telemetry",
                    name="Telemetry",
                    dimensions=dimensions,
                    datasets=[declaration],
                )
            ],
            dimensions=dimensions,
        )
    else:
        spec_definition = spec.from_python(
            datasets=[declaration], dimensions=dimensions, name="telemetry"
        )
    assert spec_definition.entities["telemetry"].datasets["observations"].order == (
        _parse(tmp_path, ORDER).entities["telemetry"].datasets["observations"].order
    )
    path = tmp_path / "python.json"
    spec.write_document(spec_definition, path)
    assert spec.load_spec(path).entities["telemetry"].datasets["observations"].order == [
        spec.Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    with pytest.raises(pydantic.ValidationError):
        python_spec.dataset.Order(
            dimension=python_spec.ref.feature("machine"), direction="asc"
        ).to_model()

    with pytest.raises(validation.SpecError, match="not declared by entity"):
        spec.from_python(
            datasets=[
                python_spec.dataset.Dataset(
                    id="observations",
                    order=[
                        python_spec.dataset.Order(
                            dimension=python_spec.ref.dimension("missing"),
                            direction="asc",
                        )
                    ],
                )
            ]
        )


def test_dataset_order_appears_in_html(tmp_path: pathlib.Path) -> None:
    spec_definition = _parse(tmp_path, ORDER)
    render_explorer(spec_definition, tmp_path / "index.html")
    html = (tmp_path / "spec/datasets.html").read_text(encoding="utf-8")
    assert "Logical order (not a physical row-order guarantee)" in html
    assert html.index("$dimensions.machine asc") < html.index("$dimensions.timestamp desc")
    assert "Logical order" not in (tmp_path / "spec/features.html").read_text(encoding="utf-8")


def test_dataset_order_does_not_change_plan_or_sort_engine_rows() -> None:
    identifier = python_spec.dimension.Dimension(id="id", type="integer")
    declaration = python_spec.dataset.Dataset(
        id="ordered_values",
        mappings={
            "read": python_spec.mapping.FunctionMapping(
                inputs=[],
                function=python_spec.ref.function(_read_order_data, operation="read"),
                arguments={},
                outputs=[
                    python_spec.feature.Feature(name="input_1"),
                    python_spec.feature.Feature(name="input_2"),
                    python_spec.feature.Feature(name="id", type="integer"),
                ],
            ),
            "sum": python_spec.mapping.FunctionMapping(
                inputs=[python_spec.ref.feature("input_1"), python_spec.ref.feature("input_2")],
                function=python_spec.ref.function(_sum_order_features, operation="vectorize"),
                arguments={
                    "left_feature": python_spec.ref.feature("input_1"),
                    "right_feature": python_spec.ref.feature("input_2"),
                    "output": "sum",
                    "dataset": python_spec.ref.current_dataset().dataframe,
                },
                outputs=[python_spec.feature.Feature(name="sum")],
            ),
        },
    )
    entity = python_spec.entity.Entity(
        id="order_test",
        name="Order test",
        dimensions=[identifier],
        datasets=[declaration],
    )
    unordered = spec.from_python(entities=[entity], dimensions=[identifier])
    ordered = spec.from_python(
        entities=[
            python_spec.entity.Entity(
                id=entity.id,
                name=entity.name,
                dimensions=[identifier],
                datasets=[
                    python_spec.dataset.Dataset(
                        id=declaration.id,
                        mappings=declaration.mappings,
                        order=[
                            python_spec.dataset.Order(
                                dimension=python_spec.ref.dimension("id"), direction="desc"
                            )
                        ],
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
    frame = result.datasets[declaration.id]
    assert isinstance(frame, pl.DataFrame)
    assert frame.select(_read_order_data().columns).rows() == _read_order_data().rows()
    assert frame["id"].to_list() != frame.sort("id", descending=True)["id"].to_list()
