"""Build a static documentation website from an analytics specification."""

import pathlib

from uptimely import analytics, compile, spec
from uptimely import render as uptimely_render
from uptimely.analytics import render as graph_render
from uptimely.compile import render
from uptimely.spec import render as spec_render

from . import lineage

OUTPUT_DIR = pathlib.Path("_generated") / "explorer"


class Documentation:
    """Generate a linked specification, plan, and data-lineage website."""

    def __init__(self, specification: spec.Specification) -> None:
        self.spec = specification

    def create_json(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export specification reference data as JSON.

        Args:
            output_path: Output file; defaults to ``_generated/explorer/docs.json``.
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
        """Export the complete static website with navigation between its pages.

        Compilation inspects function signatures but does not execute analytics.
        Function entrypoints must be importable, as with plan compilation.
        Individual HTML report and subset-graph exports are not supported.

        Args:
            output_path: Index file; defaults to ``_generated/explorer/index.html``.
                Section pages are written in spec, plan, and execution subdirectories
                beneath the index directory.
            include_generated_at: Include a timestamp on the specification page.

        Returns:
            The path to the website index.
        """
        target = pathlib.Path(output_path) if output_path is not None else OUTPUT_DIR / "index.html"
        target = target.with_suffix(".html")
        plan = compile.Compiler(self.spec).compile()
        graph = analytics.FeatureGraph(self.spec)
        context = spec_render._build_context(self.spec, include_generated_at)
        spec_render._create_website_pages(context, target.parent, index_filename=target.name)
        graph_render._create_website_pages(graph, target.parent, index_filename=target.name)
        render._create_website_pages(plan, target.parent, index_filename=target.name)
        lineage._create_website_page(self.spec, plan, target.parent, index_filename=target.name)
        document = (
            uptimely_render.html_environment()
            .get_template("index.html.j2")
            .render(
                specification=self.spec,
                summary=context.summary,
                operation_count=len(plan.operations),
                stage_count=len(plan.execution_stages),
                index_filename=target.name,
                include_navigation=True,
                active_page="home",
                root_path="",
            )
        )
        target.write_text(document, encoding="utf-8")
        for filename in (
            "feature_graph_2d.html",
            "feature_graph_3d.html",
            "execution_plan_graph_2d.html",
            "execution_plan_graph_3d.html",
            "graph/feature_graph.html",
        ):
            obsolete_page = target.parent / filename
            if obsolete_page != target:
                obsolete_page.unlink(missing_ok=True)
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
    """Export the complete documentation website.

    Args:
        specification: The canonical analytics specification.
        output_path: Index file; defaults to ``_generated/explorer/index.html``.
        include_generated_at: Include a timestamp on specification pages.

    Returns:
        The path to the website index.
    """
    return Documentation(specification).create_html(output_path, include_generated_at)
