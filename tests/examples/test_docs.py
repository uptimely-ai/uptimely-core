import json
from html.parser import HTMLParser
from pathlib import Path

from uptimely.docs.docs import Documentation
from uptimely.spec import Specification

SPEC_PATH = Path("examples/example_1/generated/spec/spec.json")
FRAGMENT_OPERATIONS = ("read", "conform", "expand", "collapse")


class TextCollector(HTMLParser):
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


def _documentation_counts(specification: Specification) -> dict[str, int]:
    datasets = [
        dataset for entity in specification.entities.values() for dataset in entity.datasets
    ]
    feature_count = sum(
        len(fragment.features)
        for dataset in datasets
        for operation in FRAGMENT_OPERATIONS
        for fragment in getattr(dataset, operation).values()
    ) + sum(len(dataset.vectorize) for dataset in datasets)
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


def test_json_docs_have_expected_keys(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)

    output_path = Documentation(specification).create_json(tmp_path / "docs.json")
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
        "fragment_count",
        "dimension_count",
        "feature_count",
        "bound_feature_count",
        "function_count",
        "feature_buckets",
        "vectorized_feature_count",
        "function_buckets",
    }


def test_json_docs_counts_match_specification(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    expected_counts = _documentation_counts(specification)

    output_path = Documentation(specification).create_json(tmp_path / "docs.json")
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


def test_html_docs_overview_counts_match_specification(tmp_path: Path) -> None:
    specification = Specification.from_json(SPEC_PATH)
    expected_counts = _documentation_counts(specification)

    output_path = Documentation(specification).create_html(tmp_path / "docs.html")
    parser = TextCollector()
    parser.feed(output_path.read_text(encoding="utf-8"))

    assert f"Entities {expected_counts['entity_count']}" in parser.text
    assert f"Dimensions {expected_counts['dimension_count']}" in parser.text
    assert f"Features total {expected_counts['feature_count']}" in parser.text
    assert f"Functions total {expected_counts['function_count']}" in parser.text
