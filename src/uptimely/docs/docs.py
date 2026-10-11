"""Build a static documentation website from an analytics specification."""

from pathlib import Path

from uptimely.analytics import FeatureGraph
from uptimely.compile import Compiler
from uptimely.render import html_environment
from uptimely.spec import Specification
from uptimely.spec.render import create_json as create_specification_json

OUTPUT_DIR = Path("_generated") / "docs"


class Documentation:
    """Generate a linked specification, feature graph, and execution plan website."""

    def __init__(self, specification: Specification) -> None:
        self.spec = specification

    def create_json(
        self,
        output_path: str | Path | None = None,
        include_generated_at: bool = False,
    ) -> Path:
        """Export specification reference data as JSON.

        Args:
            output_path: Output file; defaults to ``_generated/docs/docs.json``.
            include_generated_at: Include a build timestamp.

        Returns:
            The path to the JSON document.
        """
        target = Path(output_path) if output_path is not None else OUTPUT_DIR / "docs.json"
        return create_specification_json(self.spec, target, include_generated_at)

    def create_html(
        self,
        output_path: str | Path | None = None,
        include_generated_at: bool = False,
    ) -> Path:
        """Export a static website with navigation between generated reports.

        Compilation inspects function signatures but does not execute analytics.
        Function entrypoints must be importable, as with standalone plan compilation.

        Args:
            output_path: Index file; defaults to ``_generated/docs/index.html``.
                All three report pages are written alongside this file.
            include_generated_at: Include a timestamp on the specification page.

        Returns:
            The path to the website index.

        Raises:
            ValueError: If the index path conflicts with a report filename.
        """
        target = Path(output_path) if output_path is not None else OUTPUT_DIR / "index.html"
        target = target.with_suffix(".html")
        if target.name in {"spec.html", "feature_graph.html", "execution_plan.html"}:
            raise ValueError("The website index path must not overwrite a report page.")
        plan = Compiler(self.spec).compile()
        graph = FeatureGraph(self.spec)
        self.spec.create_html(
            target.parent / "spec.html",
            include_generated_at,
            include_navigation=True,
        )
        graph.export_html(target.parent / "feature_graph.html", include_navigation=True)
        plan.export_html(target.parent / "execution_plan.html", include_navigation=True)
        document = (
            html_environment("docs/templates")
            .get_template("index.html.j2")
            .render(
                specification=self.spec,
                include_navigation=True,
                active_page="home",
            )
        )
        target.write_text(document, encoding="utf-8")
        return target


def create_json(
    specification: Specification,
    output_path: str | Path | None = None,
    include_generated_at: bool = False,
) -> Path:
    """Export specification reference data as JSON."""
    return Documentation(specification).create_json(output_path, include_generated_at)


def create_html(
    specification: Specification,
    output_path: str | Path | None = None,
    include_generated_at: bool = False,
) -> Path:
    """Export the linked documentation website and return its index path."""
    return Documentation(specification).create_html(output_path, include_generated_at)
