"""Build an analytics explorer website."""

import pathlib

from uptimely import analytics, compiler
from uptimely import render as uptimely_render

from . import analytics_render, graph_render, lineage, plan_render

EXPLORER_OUTPUT_DIR = pathlib.Path("_generated") / "explorer"


class Explorer:
    """Generate a linked analytics, plan, and data-lineage website."""

    def __init__(self, analytics_definition: analytics.Analytics) -> None:
        self.analytics = analytics_definition

    def create_json(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export analytics reference data as JSON.

        Args:
            output_path: Output file; defaults to ``_generated/explorer/explorer.json``.
            include_generated_at: Include a build timestamp.

        Returns:
            The path to the JSON document.
        """
        target = (
            pathlib.Path(output_path)
            if output_path is not None
            else EXPLORER_OUTPUT_DIR / "explorer.json"
        )
        return analytics_render.create_json(self.analytics, target, include_generated_at)

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
                Section pages are written in analytics, plan, and execution subdirectories
                beneath the index directory.
            include_generated_at: Include a timestamp on the analytics page.

        Returns:
            The path to the website index.
        """
        target = (
            pathlib.Path(output_path)
            if output_path is not None
            else EXPLORER_OUTPUT_DIR / "index.html"
        )
        target = target.with_suffix(".html")
        plan = compiler.Compiler(self.analytics).compile()
        graph = analytics.FeatureGraph(self.analytics)
        context = analytics_render._build_context(self.analytics, include_generated_at)
        analytics_render._create_website_pages(context, target.parent, index_filename=target.name)
        graph_render._create_website_pages(graph, target.parent, index_filename=target.name)
        plan_render._create_website_pages(plan, target.parent, index_filename=target.name)
        lineage._create_website_page(
            self.analytics, plan, target.parent, index_filename=target.name
        )
        document = (
            uptimely_render.html_environment()
            .get_template("index.html.j2")
            .render(
                analytics_definition=self.analytics,
                summary=context.summary,
                callable_count=len(plan.callables),
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
    analytics_definition: analytics.Analytics,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Export analytics reference data as JSON."""
    return Explorer(analytics_definition).create_json(output_path, include_generated_at)


def create_html(
    analytics_definition: analytics.Analytics,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Export the complete analytics explorer website.

    Args:
        analytics_definition: The analytics document model.
        output_path: Index file; defaults to ``_generated/explorer/index.html``.
        include_generated_at: Include a timestamp on analytics pages.

    Returns:
        The path to the website index.
    """
    return Explorer(analytics_definition).create_html(output_path, include_generated_at)
