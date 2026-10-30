import dataclasses
import pathlib
from html import parser as html_parser
from urllib import parse as url_parse

import pytest
from examples.pump_analytics.spec import spec as pump_analytics_module
from support import examples as example_support
from support import rendering as rendering_support

from uptimely import compiler, project, spec
from uptimely.explorer import render
from uptimely.explorer.sections import spec as spec_render

SPEC_PATH = example_support.EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"

CATALOG_PAGES = (
    "spec/features.html",
    "spec/datasets.html",
    "spec/dimensions.html",
    "spec/entities.html",
    "spec/functions.html",
    "plan/stages.html",
)


class ContextLinksCollector(html_parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.item_ids: list[str] = []
        self.links: list[str] = []
        self.statistics: dict[str, int] = {}
        self.current_statistic: str | None = None
        self.in_context = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if label := attributes.get("data-stat"):
            self.current_statistic = label
        if (value := attributes.get("data-value")) is not None and self.current_statistic:
            self.statistics[self.current_statistic] = int(value)
        if identifier := attributes.get("id"):
            self.ids.append(identifier)
            if "data-context-item" in attributes:
                self.item_ids.append(identifier)
            if identifier == "catalog-context":
                self.in_context = True
        if self.in_context and tag == "a" and (href := attributes.get("href")):
            self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "aside":
            self.in_context = False


def test_catalog_context_links_resolve_to_all_cards_and_stages(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    rendering_support.render_explorer(
        pump_bundle.spec_definition, tmp_path / "index.html", plan=pump_bundle.execution_plan
    )
    prefixes = ("feature-", "dataset-", "dimension-", "entity-", "function-", "stage-")
    expected_statistics = (
        (
            "Features",
            sum(
                len(
                    {
                        reference.removeprefix("$features.")
                        for action in dataset.actions.values()
                        for reference in action.features.outputs
                    }
                    - set(entity.dimension_ids)
                )
                for entity in pump_bundle.spec_definition.entities.values()
                for dataset in entity.datasets.values()
            ),
        ),
        (
            "Datasets",
            sum(len(entity.datasets) for entity in pump_bundle.spec_definition.entities.values()),
        ),
        ("Dimensions", len(pump_bundle.spec_definition.dimensions)),
        ("Entities", len(pump_bundle.spec_definition.entities)),
        ("Functions", len(pump_bundle.spec_definition.functions)),
        ("Stages", len(pump_bundle.execution_plan.execution_stages)),
    )
    for filename, prefix, (label, count) in zip(
        CATALOG_PAGES, prefixes, expected_statistics, strict=True
    ):
        document = (tmp_path / filename).read_text(encoding="utf-8")
        collector = ContextLinksCollector()
        collector.feed(document)
        assert len(collector.ids) == len(set(collector.ids))
        assert "catalog-context" in collector.ids
        assert collector.links
        assert collector.links[0] == "#catalog-overview"
        assert collector.item_ids[0] == "catalog-overview"
        assert collector.statistics[label] == count
        assert document.index("<h1 ") < document.index('id="catalog-overview"')
        targets = [url_parse.unquote(link.removeprefix("#")) for link in collector.links]
        assert all(link.startswith("#") for link in collector.links)
        assert all(target in collector.ids for target in targets)
        assert collector.item_ids
        assert set(collector.item_ids) <= set(targets)
        assert {target for target in targets if target.startswith(prefix)} == {
            identifier for identifier in collector.ids if identifier.startswith(prefix)
        }
        assert 'aria-controls="catalog-context"' in document
        assert 'class="nav-label-toggle context-label-toggle"' in document
        assert 'src="../js/catalog_context.js"' in document
        assert "Spec reference" not in document

    for filename in (
        "index.html",
        "spec/overview.html",
        "plan/overview.html",
    ):
        assert 'id="catalog-context"' not in (tmp_path / filename).read_text(encoding="utf-8")

    for filename in ("spec/feature-lineage.html", "plan/invocation-lineage.html"):
        document = (tmp_path / filename).read_text(encoding="utf-8")
        assert 'id="lineage-context"' in document
        assert 'id="catalog-context"' not in document


def test_empty_catalog_context_panels(tmp_path: pathlib.Path) -> None:
    definition = spec.Spec()
    rendering_support.render_explorer(
        definition, tmp_path / "index.html", plan=compiler.Compiler().compile(definition)
    )
    for filename in CATALOG_PAGES:
        document = (tmp_path / filename).read_text(encoding="utf-8")
        collector = ContextLinksCollector()
        collector.feed(document)
        assert "catalog-context" in collector.ids
        assert collector.links == ["#catalog-overview"]
        assert collector.item_ids == ["catalog-overview"]
        assert 'class="context-empty">No ' in document


def test_context_links_escape_labels_and_encode_fragments() -> None:
    template = render.html_environment().get_template("base.html.j2")
    document = template.render(
        include_navigation=True,
        active_page="spec",
        active_section="entities",
        configuration={"entities": {'a&b"#c': {"name": "<Entity>"}}},
    )
    assert "&lt;Entity&gt;" in document
    assert 'href="#entity-a%26b%22%23c"' in document


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


@pytest.mark.usefixtures("example_projects")
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


@pytest.mark.usefixtures("example_projects")
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


def test_html_explorer_overview_counts_match_spec(
    tmp_path: pathlib.Path, pump_bundle: project.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    spec_definition.name = "Pump analytics"
    expected_counts = _explorer_counts(spec_definition)

    rendering_support.render_explorer(
        spec_definition, tmp_path / "index.html", plan=compiler.Compiler().compile(spec_definition)
    )
    output_path = tmp_path / "spec/overview.html"
    parser = TextCollector()
    parser.feed(output_path.read_text(encoding="utf-8"))

    assert "Spec profile Pump analytics" in parser.text
    assert f"Entities {expected_counts['entity_count']}" in parser.text
    assert f"Dimensions {expected_counts['dimension_count']}" in parser.text
    assert f"Features total {expected_counts['feature_count']}" in parser.text
    assert f"Functions total {expected_counts['function_count']}" in parser.text
