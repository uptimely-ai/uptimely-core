import json
import pathlib
from html import parser as html_parser

from examples.pump_analytics.config.spec import spec as pump_spec

from uptimely import analytics as spec
from uptimely.explorer import explorer

SPEC_PATH = pathlib.Path("examples/pump_analytics/_generated/spec/spec.json")


def test_specification_exports_only_json(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_python(
        entities=pump_spec.entities,
        dimensions=pump_spec.dimensions,
        name="Pump analytics",
    )
    specification.to_json(tmp_path / "spec.json")

    assert {path.name for path in tmp_path.iterdir()} == {"spec.json"}
    assert spec.Specification.from_json(tmp_path / "spec.json").name == "Pump analytics"


class TextCollector(html_parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def _explorer_counts(specification: spec.Specification) -> dict[str, int]:
    datasets = [
        dataset for entity in specification.entities.values() for dataset in entity.datasets
    ]
    feature_count = sum(len(dataset.features) for dataset in datasets)
    function_count = sum(
        len(functions)
        for functions in specification.functions.model_dump(exclude_none=True).values()
    )
    return {
        "entity_count": len(specification.entities),
        "dataset_count": len(datasets),
        "dimension_count": len(specification.dimensions),
        "feature_count": feature_count,
        "function_count": function_count,
    }


def test_json_explorer_have_expected_keys(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)

    output_path = explorer.Explorer(specification).create_json(tmp_path / "explorer.json")
    document = json.loads(output_path.read_text(encoding="utf-8"))

    assert set(document) == {
        "configuration",
        "summary",
        "feature_dependencies",
        "generated_at",
    }
    assert set(document["configuration"]) == set(
        specification.model_dump(mode="json", exclude_none=True)
    )
    assert set(document["summary"]) == {
        "entity_count",
        "dataset_count",
        "mapping_count",
        "dimension_count",
        "feature_count",
        "bound_feature_count",
        "function_count",
        "feature_buckets",
        "vectorized_feature_count",
        "function_buckets",
    }


def test_json_explorer_counts_match_specification(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    expected_counts = _explorer_counts(specification)

    output_path = explorer.Explorer(specification).create_json(tmp_path / "explorer.json")
    document = json.loads(output_path.read_text(encoding="utf-8"))
    configuration = document["configuration"]

    assert len(configuration["entities"]) == expected_counts["entity_count"]
    assert len(configuration["dimensions"]) == expected_counts["dimension_count"]
    assert (
        sum(len(entity["datasets"]) for entity in configuration["entities"].values())
        == expected_counts["dataset_count"]
    )
    assert document["summary"] | expected_counts == document["summary"]
    assert len(document["feature_dependencies"]) == len(specification.calls)


def test_html_explorer_overview_counts_match_specification(tmp_path: pathlib.Path) -> None:
    specification = spec.Specification.from_json(SPEC_PATH)
    specification.name = "Pump analytics"
    expected_counts = _explorer_counts(specification)

    explorer.Explorer(specification).create_html(tmp_path / "index.html")
    output_path = tmp_path / "spec/overview.html"
    parser = TextCollector()
    parser.feed(output_path.read_text(encoding="utf-8"))

    assert "Specification profile Pump analytics" in parser.text
    assert f"Entities {expected_counts['entity_count']}" in parser.text
    assert f"Dimensions {expected_counts['dimension_count']}" in parser.text
    assert f"Features total {expected_counts['feature_count']}" in parser.text
    assert f"Functions total {expected_counts['function_count']}" in parser.text
