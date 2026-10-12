"""Build a static documentation website from an analytics specification."""

import pathlib

from uptimely import analytics, compile, spec
from uptimely import render as uptimely_render
from uptimely.compile import render
from uptimely.spec import render as spec_render

OUTPUT_DIR = pathlib.Path("_generated") / "docs"


class Documentation:
    """Generate a linked specification, feature graph, and execution plan website."""

    def __init__(self, specification: spec.Specification) -> None:
        self.spec = specification

    def create_json(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export specification reference data as JSON.

        Args:
            output_path: Output file; defaults to ``_generated/docs/docs.json``.
            include_generated_at: Include a build timestamp.

        Returns:
            The path to the JSON document.
        """
        target = pathlib.Path(output_path) if output_path is not None else OUTPUT_DIR / "docs.json"
        return spec_render.create_json(self.spec, target, include_generated_at)

    def create_html(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export a static website with navigation between generated reports.

        Compilation inspects function signatures but does not execute analytics.
        Function entrypoints must be importable, as with standalone plan compilation.

        Args:
            output_path: Index file; defaults to ``_generated/docs/index.html``.
                All report and specification section pages are written alongside this file.
            include_generated_at: Include a timestamp on the specification page.

        Returns:
            The path to the website index.

        Raises:
            ValueError: If the index path conflicts with a report filename.
        """
        target = pathlib.Path(output_path) if output_path is not None else OUTPUT_DIR / "index.html"
        target = target.with_suffix(".html")
        if target.name in {
            *spec_render.SPECIFICATION_PAGES.values(),
            "2d.html",
            "3d.html",
            *render.PLAN_PAGES.values(),
        }:
            raise ValueError("The website index path must not overwrite a report page.")
        plan = compile.Compiler(self.spec).compile()
        graph = analytics.FeatureGraph(self.spec)
        spec_dir = target.parent / "spec"
        graph_dir = target.parent / "graph"
        plan_dir = target.parent / "plan"
        spec_render.create_website_pages(self.spec, spec_dir, include_generated_at, root_path="../")
        for dimension in ("2d", "3d"):
            graph.export_html(
                graph_dir / f"{dimension}.html",
                dimension=dimension,
                include_navigation=True,
                root_path="../",
            )
        plan.export_html(
            plan_dir / "overview.html",
            include_navigation=True,
            root_path="../",
        )
        document = (
            uptimely_render.html_environment()
            .get_template("index.html.j2")
            .render(
                specification=self.spec,
                include_navigation=True,
                active_page="home",
                root_path="",
            )
        )
        target.write_text(document, encoding="utf-8")
        return target


def create_json(
    specification: spec.Specification,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Export specification reference data as JSON."""
    return Documentation(specification).create_json(output_path, include_generated_at)


def create_html(
    specification: spec.Specification,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Export the linked documentation website and return its index path."""
    return Documentation(specification).create_html(output_path, include_generated_at)
