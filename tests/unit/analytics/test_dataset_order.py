import dataclasses
import json
import pathlib
import typing

import polars as pl
import pydantic
import pytest
from examples.simple_analytics.config.analytics import analytics as analytics_module
from examples.simple_analytics.functions import functions

from uptimely import analytics, compile, engine
from uptimely.analytics import python as python_analytics
from uptimely.analytics import validation
from uptimely.explorer import explorer

ORDER = [
    {"dimension": "$dimensions.machine", "direction": "asc"},
    {"dimension": "$dimensions.timestamp", "direction": "desc"},
]


def _configuration() -> dict[str, typing.Any]:
    return {
        "version": "0.1.0",
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
                "datasets": [{"id": "observations", "order": ORDER}],
            }
        },
    }


def _parse(tmp_path: pathlib.Path, order: object) -> analytics.Analytics:
    configuration = _configuration()
    configuration["entities"]["telemetry"]["datasets"][0]["order"] = order
    path = tmp_path / "input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return analytics.Analytics(json=path)


def test_dataset_order_json_round_trip_preserves_precedence(tmp_path: pathlib.Path) -> None:
    analytics_definition = _parse(tmp_path, ORDER)
    keys = analytics_definition.entities["telemetry"].datasets[0].order
    assert keys == [analytics.Order(**key) for key in ORDER]

    path = tmp_path / "export.json"
    analytics_definition.to_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entities"]["telemetry"]["datasets"][0]["order"] == ORDER
    assert analytics.Analytics(json=path).entities["telemetry"].datasets[0].order == keys


def test_dataset_order_defaults_to_empty_without_shared_state(tmp_path: pathlib.Path) -> None:
    assert _parse(tmp_path, []).entities["telemetry"].datasets[0].order == []
    configuration = _configuration()
    del configuration["entities"]["telemetry"]["datasets"][0]["order"]
    path = tmp_path / "omitted.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    assert analytics.Analytics(json=path).entities["telemetry"].datasets[0].order == []

    first = analytics.Dataset(id="first")
    second = analytics.Dataset(id="second")
    first.order.append(analytics.Order(**ORDER[0]))
    assert second.order == []
    assert (
        python_analytics.dataset.Dataset(id="first").order
        is not python_analytics.dataset.Dataset(id="second").order
    )


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
    with pytest.raises(validation.AnalyticsError) as error:
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
    with pytest.raises(validation.AnalyticsError) as error:
        _parse(tmp_path, [ORDER[0], {"dimension": "$dimensions.machine", "direction": direction}])

    assert error.value.code == "duplicate_order_dimension"
    assert error.value.path[-3:] == ("order", 1, "dimension")


@pytest.mark.parametrize("use_entities", [True, False])
def test_dataset_order_python_authoring_matches_json(
    tmp_path: pathlib.Path, use_entities: bool
) -> None:
    declaration = python_analytics.dataset.Dataset(
        id="observations",
        order=[
            python_analytics.dataset.Order(
                dimension=python_analytics.ref.dimension("machine"), direction="asc"
            ),
            python_analytics.dataset.Order(dimension="$dimensions.timestamp", direction="desc"),
        ],
    )
    dimensions = [
        python_analytics.dimension.Dimension(id="machine", type="string"),
        python_analytics.dimension.Dimension(id="timestamp", type="datetime"),
    ]
    if use_entities:
        analytics_definition = analytics.Analytics.from_python(
            entities=[
                python_analytics.entity.Entity(
                    id="telemetry",
                    name="Telemetry",
                    dimensions=dimensions,
                    datasets=[declaration],
                )
            ],
            dimensions=dimensions,
        )
    else:
        analytics_definition = analytics.Analytics.from_python(
            datasets=[declaration], dimensions=dimensions, name="telemetry"
        )
    assert analytics_definition.entities["telemetry"].datasets[0].order == (
        _parse(tmp_path, ORDER).entities["telemetry"].datasets[0].order
    )
    path = tmp_path / "python.json"
    analytics_definition.to_json(path)
    assert analytics.Analytics(json=path).entities["telemetry"].datasets[0].order == [
        analytics.Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    with pytest.raises(pydantic.ValidationError):
        python_analytics.dataset.Order(
            dimension=python_analytics.ref.feature("machine"), direction="asc"
        ).to_model()

    with pytest.raises(validation.AnalyticsError, match="not declared by entity"):
        analytics.Analytics.from_python(
            datasets=[
                python_analytics.dataset.Dataset(
                    id="observations",
                    order=[
                        python_analytics.dataset.Order(
                            dimension=python_analytics.ref.dimension("missing"),
                            direction="asc",
                        )
                    ],
                )
            ]
        )


def test_dataset_order_appears_in_reference_json_and_html(tmp_path: pathlib.Path) -> None:
    analytics_definition = _parse(tmp_path, ORDER)
    path = explorer.Explorer(analytics_definition).create_json(tmp_path / "explorer.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["configuration"]["entities"]["telemetry"]["datasets"][0]["order"] == ORDER

    explorer.Explorer(analytics_definition).create_html(tmp_path / "index.html")
    html = (tmp_path / "spec/datasets.html").read_text(encoding="utf-8")
    assert "Logical order (not a physical row-order guarantee)" in html
    assert html.index("$dimensions.machine asc") < html.index("$dimensions.timestamp desc")
    assert "Logical order" not in (tmp_path / "spec/features.html").read_text(encoding="utf-8")


def test_dataset_order_does_not_change_plan_or_sort_engine_rows() -> None:
    declaration = python_analytics.dataset.Dataset(
        id=analytics_module.dataset_.id,
        features=[
            python_analytics.feature.Feature(id="input_1"),
            python_analytics.feature.Feature(id="input_2"),
            python_analytics.feature.Feature(id="id", type="integer"),
            python_analytics.feature.Feature(id="sum"),
        ],
        mappings=[
            python_analytics.mapping.Read(
                id="read",
                bind=python_analytics.bind.bind(python_analytics.ref.function(functions.read_data)),
                outputs=[
                    python_analytics.ref.feature("input_1"),
                    python_analytics.ref.feature("input_2"),
                    python_analytics.ref.feature("id"),
                ],
            ),
            python_analytics.mapping.Vectorize(
                id="sum",
                bind=python_analytics.bind.bind(
                    python_analytics.ref.function(functions.sum_features),
                    left_feature=python_analytics.ref.feature("input_1"),
                    right_feature=python_analytics.ref.feature("input_2"),
                    output="sum",
                    dataset=python_analytics.ref.current_dataset().dataframe,
                ),
                inputs=[
                    python_analytics.ref.feature("input_1"),
                    python_analytics.ref.feature("input_2"),
                ],
                outputs=[python_analytics.ref.feature("sum")],
            ),
        ],
    )
    unordered = analytics.Analytics.from_python(
        datasets=[declaration], dimensions=analytics_module.dimensions
    )
    ordered = analytics.Analytics.from_python(
        datasets=[
            dataclasses.replace(
                declaration,
                order=[
                    python_analytics.dataset.Order(
                        dimension=python_analytics.ref.dimension("id"), direction="desc"
                    )
                ],
            )
        ],
        dimensions=analytics_module.dimensions,
    )
    assert (
        compile.Compiler(ordered).compile().operations
        == compile.Compiler(unordered).compile().operations
    )

    result = engine.Engine(ordered).execute()
    assert result.failures == {}
    frame = result.datasets[("entity", declaration.id)]
    assert isinstance(frame, pl.DataFrame)
    assert frame.select(functions.read_data().columns).rows() == functions.read_data().rows()
    assert frame["id"].to_list() != frame.sort("id", descending=True)["id"].to_list()
