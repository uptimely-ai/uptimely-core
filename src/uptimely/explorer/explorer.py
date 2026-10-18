"""Build an analytics explorer website."""

import pathlib

from uptimely import compiler, project, spec
from uptimely import render as uptimely_render
from uptimely.compiler import plan as plan_module

from . import graph_render, lineage, plan_render, spec_render


class Explorer:
    """Generate a linked spec, plan, and data-lineage website.

    Args:
        spec_definition: Spec document for model and feature pages.
        plan: Existing plan for plan and lineage pages; compile when omitted.
            Supply a plan built from the same spec document.
    """

    def __init__(
        self,
        spec_definition: spec.Spec,
        *,
        plan: plan_module.ExecutionPlan | None = None,
    ) -> None:
        self.spec = spec_definition
        self.plan = plan

    def create_html(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export the complete static website with navigation between its pages.

        A supplied plan is rendered without recompilation. Otherwise compilation
        inspects function signatures but does not execute spec.
        Function metadata inspection may import entrypoints in either mode.
        Individual HTML report and subset-graph exports are not supported.

        Args:
            output_path: Index file; defaults to ``project.EXPLORER_INDEX_FILE``.
                Section pages are written in spec, plan, and execution subdirectories
                beneath the index directory.
            include_generated_at: Include a timestamp on the spec page.

        Returns:
            The path to the website index.
        """
        target = (
            pathlib.Path(output_path) if output_path is not None else project.EXPLORER_INDEX_FILE
        )
        target = target.with_suffix(".html")
        plan = self.plan if self.plan is not None else compiler.Compiler(self.spec).compile()
        graph = spec.FeatureGraph(self.spec)
        context = spec_render._build_context(self.spec, include_generated_at)
        spec_render._create_website_pages(context, target.parent, index_filename=target.name)
        graph_render._create_website_pages(graph, target.parent, index_filename=target.name)
        plan_render._create_website_pages(plan, target.parent, index_filename=target.name)
        lineage._create_website_page(self.spec, plan, target.parent, index_filename=target.name)
        document = (
            uptimely_render.html_environment()
            .get_template("index.html.j2")
            .render(
                spec_definition=self.spec,
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


def create_html(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
    *,
    plan: plan_module.ExecutionPlan | None = None,
) -> pathlib.Path:
    """Export the complete analytics explorer website.

    Args:
        spec_definition: The spec document model.
        output_path: Index file; defaults to ``project.EXPLORER_INDEX_FILE``.
        include_generated_at: Include a timestamp on spec pages.
        plan: Existing execution plan to render; compile spec when omitted.

    Returns:
        The path to the website index.
    """
    return Explorer(spec_definition, plan=plan).create_html(output_path, include_generated_at)
