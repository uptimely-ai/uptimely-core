import json
import pathlib
from html import parser as html_parser

from examples.pump_analytics.config.analytics import analytics as pump_analytics_module

from uptimely import analytics
from uptimely.explorer import explorer

ANALYTICS_PATH = pathlib.Path("examples/pump_analytics/_generated/analytics/analytics.json")


def test_analytics_exports_only_json(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics.from_python(
        entities=pump_analytics_module.entities,
        dimensions=pump_analytics_module.dimensions,
        name="Pump analytics",
    )
    analytics_definition.to_json(tmp_path / "analytics.json")

    assert {path.name for path in tmp_path.iterdir()} == {"analytics.json"}
    assert analytics.Analytics(json=tmp_path / "analytics.json").name == "Pump analytics"


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


def _explorer_counts(analytics_definition: analytics.Analytics) -> dict[str, int]:
    datasets = [
        dataset for entity in analytics_definition.entities.values() for dataset in entity.datasets
    ]
    feature_count = sum(len(dataset.features) for dataset in datasets)
    function_count = sum(
        len(functions)
        for functions in analytics_definition.functions.model_dump(exclude_none=True).values()
    )
    return {
        "entity_count": len(analytics_definition.entities),
        "dataset_count": len(datasets),
        "dimension_count": len(analytics_definition.dimensions),
        "feature_count": feature_count,
        "function_count": function_count,
    }


def test_json_explorer_have_expected_keys(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)

    output_path = explorer.Explorer(analytics_definition).create_json(tmp_path / "explorer.json")
    document = json.loads(output_path.read_text(encoding="utf-8"))

    assert set(document) == {
        "configuration",
        "summary",
        "feature_dependencies",
        "generated_at",
    }
    assert set(document["configuration"]) == set(
        analytics_definition.model_dump(mode="json", exclude_none=True)
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


def test_json_explorer_counts_match_analytics(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    expected_counts = _explorer_counts(analytics_definition)

    output_path = explorer.Explorer(analytics_definition).create_json(tmp_path / "explorer.json")
    document = json.loads(output_path.read_text(encoding="utf-8"))
    configuration = document["configuration"]

    assert len(configuration["entities"]) == expected_counts["entity_count"]
    assert len(configuration["dimensions"]) == expected_counts["dimension_count"]
    assert (
        sum(len(entity["datasets"]) for entity in configuration["entities"].values())
        == expected_counts["dataset_count"]
    )
    assert document["summary"] | expected_counts == document["summary"]
    assert len(document["feature_dependencies"]) == len(analytics_definition.calls)


def test_html_explorer_overview_counts_match_analytics(tmp_path: pathlib.Path) -> None:
    analytics_definition = analytics.Analytics(json=ANALYTICS_PATH)
    analytics_definition.name = "Pump analytics"
    expected_counts = _explorer_counts(analytics_definition)

    explorer.Explorer(analytics_definition).create_html(tmp_path / "index.html")
    output_path = tmp_path / "analytics/overview.html"
    parser = TextCollector()
    parser.feed(output_path.read_text(encoding="utf-8"))

    assert "Analytics profile Pump analytics" in parser.text
    assert f"Entities {expected_counts['entity_count']}" in parser.text
    assert f"Dimensions {expected_counts['dimension_count']}" in parser.text
    assert f"Features total {expected_counts['feature_count']}" in parser.text
    assert f"Functions total {expected_counts['function_count']}" in parser.text
