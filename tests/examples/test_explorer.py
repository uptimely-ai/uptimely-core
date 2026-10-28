import dataclasses
import pathlib
from html import parser as html_parser

from conftest import EXAMPLES_ROOT, render_explorer
from examples.pump_analytics.spec import spec as pump_analytics_module

from uptimely import spec
from uptimely.explorer.sections import spec as spec_render

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_spec_exports_only_json(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.from_python(
        entities=pump_analytics_module.python_spec.entities,
        dimensions=pump_analytics_module.python_spec.dimensions,
        name="Pump analytics",
    )
    spec.write_document(spec_definition, tmp_path / "spec.json")

    assert {path.name for path in tmp_path.iterdir()} == {"spec.json"}
    assert spec.load_spec(tmp_path / "spec.json").name == "Pump analytics"


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


def _explorer_counts(spec_definition: spec.Spec) -> dict[str, int]:
    datasets = [
        dataset
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
    ]
    feature_count = sum(len(dataset.features) for dataset in datasets)
    function_count = len(spec_definition.functions)
    return {
        "entity_count": len(spec_definition.entities),
        "dataset_count": len(datasets),
        "dimension_count": len(spec_definition.dimensions),
        "feature_count": feature_count,
        "function_count": function_count,
    }


def test_explorer_context_has_expected_fields() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    context = spec_render._build_context(spec_definition, False)
    document = dataclasses.asdict(context)

    assert set(document) == {
        "configuration",
        "summary",
        "feature_dependencies",
        "generated_at",
    }
    assert set(document["configuration"]) == set(
        spec_definition.model_dump(mode="json", exclude_none=True)
    )
    assert set(document["summary"]) == {
        "entity_count",
        "dataset_count",
        "action_count",
        "dimension_count",
        "feature_count",
        "bound_feature_count",
        "function_count",
        "feature_buckets",
        "vectorized_feature_count",
        "function_buckets",
    }


def test_explorer_context_counts_match_spec() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    expected_counts = _explorer_counts(spec_definition)

    context = spec_render._build_context(spec_definition, False)
    document = dataclasses.asdict(context)
    configuration = document["configuration"]

    assert len(configuration["entities"]) == expected_counts["entity_count"]
    assert len(configuration["dimensions"]) == expected_counts["dimension_count"]
    assert (
        sum(len(entity["datasets"]) for entity in configuration["entities"].values())
        == expected_counts["dataset_count"]
    )
    assert document["summary"] | expected_counts == document["summary"]
    assert document["feature_dependencies"] == [
        {
            "function": action.binding.function,
            "kind": spec_definition.functions[action.binding.function].kind,
            "feature": feature,
            "dependencies": action.input_features,
        }
        for entity in spec_definition.entities.values()
        for dataset in entity.datasets.values()
        for action in dataset.actions.values()
        if spec_definition.functions[action.binding.function].kind in {"escape", "vectorize"}
        for feature in action.output_features
    ]


def test_html_explorer_overview_counts_match_spec(tmp_path: pathlib.Path) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.name = "Pump analytics"
    expected_counts = _explorer_counts(spec_definition)

    render_explorer(spec_definition, tmp_path / "index.html")
    output_path = tmp_path / "spec/overview.html"
    parser = TextCollector()
    parser.feed(output_path.read_text(encoding="utf-8"))

    assert "Spec profile Pump analytics" in parser.text
    assert f"Entities {expected_counts['entity_count']}" in parser.text
    assert f"Dimensions {expected_counts['dimension_count']}" in parser.text
    assert f"Features total {expected_counts['feature_count']}" in parser.text
    assert f"Functions total {expected_counts['function_count']}" in parser.text
