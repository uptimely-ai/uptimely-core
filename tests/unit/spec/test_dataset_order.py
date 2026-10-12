import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from pydantic import ValidationError

from uptimely.compile import Compiler
from uptimely.docs.docs import Documentation
from uptimely.engine import Engine
from uptimely.spec import Dataset, Order, Specification
from uptimely.spec.python_spec import bind, dataset, dimension, entity, feature, ref
from uptimely.spec.render import create_website_pages
from uptimely.spec.validation import SpecificationError

ORDER = [
    {"dimension": "$dimensions.machine", "direction": "asc"},
    {"dimension": "$dimensions.timestamp", "direction": "desc"},
]


def _configuration() -> dict[str, Any]:
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


def _parse(tmp_path: Path, order: object) -> Specification:
    configuration = _configuration()
    configuration["entities"]["telemetry"]["datasets"][0]["order"] = order
    path = tmp_path / "input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return Specification.from_json(path)


def test_dataset_order_json_round_trip_preserves_precedence(tmp_path: Path) -> None:
    specification = _parse(tmp_path, ORDER)
    keys = specification.entities["telemetry"].datasets[0].order
    assert keys == [Order(**key) for key in ORDER]

    path = tmp_path / "export.json"
    specification.to_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entities"]["telemetry"]["datasets"][0]["order"] == ORDER
    assert Specification.from_json(path).entities["telemetry"].datasets[0].order == keys


def test_dataset_order_defaults_to_empty_without_shared_state(tmp_path: Path) -> None:
    assert _parse(tmp_path, []).entities["telemetry"].datasets[0].order == []
    configuration = _configuration()
    del configuration["entities"]["telemetry"]["datasets"][0]["order"]
    path = tmp_path / "omitted.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    assert Specification.from_json(path).entities["telemetry"].datasets[0].order == []

    first = Dataset(id="first")
    second = Dataset(id="second")
    first.order.append(Order(**ORDER[0]))
    assert second.order == []
    assert dataset.Dataset(id="first").order is not dataset.Dataset(id="second").order


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
def test_dataset_order_rejects_invalid_structure(tmp_path: Path, order: object) -> None:
    with pytest.raises(ValidationError):
        _parse(tmp_path, order)


@pytest.mark.parametrize("identifier", ["missing", "external", "@"])
def test_dataset_order_requires_owning_entity_dimensions(tmp_path: Path, identifier: str) -> None:
    with pytest.raises(SpecificationError) as error:
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
def test_dataset_order_rejects_repeated_dimensions(tmp_path: Path, direction: str) -> None:
    with pytest.raises(SpecificationError) as error:
        _parse(tmp_path, [ORDER[0], {"dimension": "$dimensions.machine", "direction": direction}])

    assert error.value.code == "duplicate_order_dimension"
    assert error.value.path[-3:] == ("order", 1, "dimension")


@pytest.mark.parametrize("use_entities", [True, False])
def test_dataset_order_python_authoring_matches_json(tmp_path: Path, use_entities: bool) -> None:
    declaration = dataset.Dataset(
        id="observations",
        order=[
            dataset.Order(dimension=ref.dimension("machine"), direction="asc"),
            dataset.Order(dimension="$dimensions.timestamp", direction="desc"),
        ],
    )
    dimensions = [
        dimension.Dimension(id="machine", type="string"),
        dimension.Dimension(id="timestamp", type="datetime"),
    ]
    if use_entities:
        specification = Specification.from_python(
            entities=[
                entity.Entity(
                    id="telemetry",
                    name="Telemetry",
                    dimensions=["machine", "timestamp"],
                    datasets=[declaration],
                )
            ],
            dimensions=dimensions,
        )
    else:
        specification = Specification.from_python(
            datasets=[declaration], dimensions=dimensions, name="telemetry"
        )
    assert specification.entities["telemetry"].datasets[0].order == (
        _parse(tmp_path, ORDER).entities["telemetry"].datasets[0].order
    )
    path = tmp_path / "python.json"
    specification.to_json(path)
    assert Specification.from_json(path).entities["telemetry"].datasets[0].order == [
        Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    with pytest.raises(ValidationError):
        dataset.Order(dimension=ref.feature("machine"), direction="asc").to_model()

    with pytest.raises(SpecificationError, match="not declared by entity"):
        Specification.from_python(
            datasets=[
                dataset.Dataset(
                    id="observations",
                    order=[dataset.Order(dimension=ref.dimension("missing"), direction="asc")],
                )
            ]
        )


def test_dataset_order_appears_in_reference_json_and_html(tmp_path: Path) -> None:
    specification = _parse(tmp_path, ORDER)
    path = Documentation(specification).create_json(tmp_path / "docs.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["configuration"]["entities"]["telemetry"]["datasets"][0]["order"] == ORDER

    standalone = specification.create_html(tmp_path / "standalone.html")
    create_website_pages(specification, tmp_path)
    for path in (standalone, tmp_path / "spec_datasets.html"):
        html = path.read_text(encoding="utf-8")
        assert "Logical order (not a physical row-order guarantee)" in html
        assert html.index("$dimensions.machine asc") < html.index("$dimensions.timestamp desc")
    assert 'href="#datasets"' in standalone.read_text(encoding="utf-8")
    assert "Logical order" not in (tmp_path / "spec_features.html").read_text(encoding="utf-8")


def test_dataset_order_does_not_change_plan_or_sort_engine_rows() -> None:
    from examples.example_2.functions.functions import read_data, sum_features
    from examples.example_2.spec.spec import dataset_, dimensions

    declaration = dataset.Dataset(
        id=dataset_.id,
        read=dataset_.read,
        vectorize=[
            feature.Vectorize(
                id="sum",
                bind=bind.bind(
                    sum_features,
                    left_feature=ref.feature("input_1"),
                    right_feature=ref.feature("input_2"),
                    output="sum",
                ),
            )
        ],
    )
    unordered = Specification.from_python(datasets=[declaration], dimensions=dimensions)
    ordered = Specification.from_python(
        datasets=[
            replace(
                declaration,
                order=[dataset.Order(dimension=ref.dimension("id"), direction="desc")],
            )
        ],
        dimensions=dimensions,
    )
    assert Compiler(ordered).compile().plan == Compiler(unordered).compile().plan

    result = Engine(ordered).execute()
    assert result.failures == {}
    frame = result.datasets[("entity", declaration.id)]
    assert isinstance(frame, pl.DataFrame)
    assert frame.select(read_data().columns).rows() == read_data().rows()
    assert frame["id"].to_list() != frame.sort("id", descending=True)["id"].to_list()
