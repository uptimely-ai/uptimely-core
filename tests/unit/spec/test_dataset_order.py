import dataclasses
import json
import pathlib
import typing

import polars as pl
import pydantic
import pytest
from examples.example_2.functions import functions
from examples.example_2.spec import spec as spec_module

from uptimely import compile, engine, spec
from uptimely.docs import docs
from uptimely.spec import python_spec, validation

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


def _parse(tmp_path: pathlib.Path, order: object) -> spec.Specification:
    configuration = _configuration()
    configuration["entities"]["telemetry"]["datasets"][0]["order"] = order
    path = tmp_path / "input.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return spec.Specification.from_json(path)


def test_dataset_order_json_round_trip_preserves_precedence(tmp_path: pathlib.Path) -> None:
    specification = _parse(tmp_path, ORDER)
    keys = specification.entities["telemetry"].datasets[0].order
    assert keys == [spec.Order(**key) for key in ORDER]

    path = tmp_path / "export.json"
    specification.to_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entities"]["telemetry"]["datasets"][0]["order"] == ORDER
    assert spec.Specification.from_json(path).entities["telemetry"].datasets[0].order == keys


def test_dataset_order_defaults_to_empty_without_shared_state(tmp_path: pathlib.Path) -> None:
    assert _parse(tmp_path, []).entities["telemetry"].datasets[0].order == []
    configuration = _configuration()
    del configuration["entities"]["telemetry"]["datasets"][0]["order"]
    path = tmp_path / "omitted.json"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    assert spec.Specification.from_json(path).entities["telemetry"].datasets[0].order == []

    first = spec.Dataset(id="first")
    second = spec.Dataset(id="second")
    first.order.append(spec.Order(**ORDER[0]))
    assert second.order == []
    assert (
        python_spec.dataset.Dataset(id="first").order
        is not python_spec.dataset.Dataset(id="second").order
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
    with pytest.raises(validation.SpecificationError) as error:
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
    with pytest.raises(validation.SpecificationError) as error:
        _parse(tmp_path, [ORDER[0], {"dimension": "$dimensions.machine", "direction": direction}])

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
        specification = spec.Specification.from_python(
            entities=[
                python_spec.entity.Entity(
                    id="telemetry",
                    name="Telemetry",
                    dimensions=["machine", "timestamp"],
                    datasets=[declaration],
                )
            ],
            dimensions=dimensions,
        )
    else:
        specification = spec.Specification.from_python(
            datasets=[declaration], dimensions=dimensions, name="telemetry"
        )
    assert specification.entities["telemetry"].datasets[0].order == (
        _parse(tmp_path, ORDER).entities["telemetry"].datasets[0].order
    )
    path = tmp_path / "python.json"
    specification.to_json(path)
    assert spec.Specification.from_json(path).entities["telemetry"].datasets[0].order == [
        spec.Order(**key) for key in ORDER
    ]


def test_dataset_order_python_authoring_validates_references() -> None:
    with pytest.raises(pydantic.ValidationError):
        python_spec.dataset.Order(
            dimension=python_spec.ref.feature("machine"), direction="asc"
        ).to_model()

    with pytest.raises(validation.SpecificationError, match="not declared by entity"):
        spec.Specification.from_python(
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


def test_dataset_order_appears_in_reference_json_and_html(tmp_path: pathlib.Path) -> None:
    specification = _parse(tmp_path, ORDER)
    path = docs.Documentation(specification).create_json(tmp_path / "docs.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["configuration"]["entities"]["telemetry"]["datasets"][0]["order"] == ORDER

    docs.Documentation(specification).create_html(tmp_path / "index.html")
    html = (tmp_path / "spec_datasets.html").read_text(encoding="utf-8")
    assert "Logical order (not a physical row-order guarantee)" in html
    assert html.index("$dimensions.machine asc") < html.index("$dimensions.timestamp desc")
    assert "Logical order" not in (tmp_path / "spec_features.html").read_text(encoding="utf-8")


def test_dataset_order_does_not_change_plan_or_sort_engine_rows() -> None:
    declaration = python_spec.dataset.Dataset(
        id=spec_module.dataset_.id,
        features=[
            python_spec.feature.Feature(id="input_1"),
            python_spec.feature.Feature(id="input_2"),
            python_spec.feature.Feature(id="id", type="integer"),
            python_spec.feature.Feature(id="sum"),
        ],
        mappings=[
            python_spec.mapping.Read(
                id="read",
                bind=python_spec.bind.bind(functions.read_data),
                outputs=[
                    python_spec.ref.feature("input_1"),
                    python_spec.ref.feature("input_2"),
                    python_spec.ref.feature("id"),
                ],
            ),
            python_spec.mapping.Vectorize(
                id="sum",
                bind=python_spec.bind.bind(
                    functions.sum_features,
                    left_feature=python_spec.ref.feature("input_1"),
                    right_feature=python_spec.ref.feature("input_2"),
                    output="sum",
                    dataset=python_spec.ref.current_dataset().dataframe,
                ),
                inputs=[python_spec.ref.feature("input_1"), python_spec.ref.feature("input_2")],
                outputs=[python_spec.ref.feature("sum")],
            ),
        ],
    )
    unordered = spec.Specification.from_python(
        datasets=[declaration], dimensions=spec_module.dimensions
    )
    ordered = spec.Specification.from_python(
        datasets=[
            dataclasses.replace(
                declaration,
                order=[
                    python_spec.dataset.Order(
                        dimension=python_spec.ref.dimension("id"), direction="desc"
                    )
                ],
            )
        ],
        dimensions=spec_module.dimensions,
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
