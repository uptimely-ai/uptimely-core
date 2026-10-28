"""Build an analytics explorer website."""

import pathlib

from uptimely import execution_plan, project_paths, spec

from . import render
from .sections import data_lineage, feature_lineage
from .sections import plan as plan_section
from .sections import spec as spec_section


class Explorer:
    """Generate a linked spec, feature-lineage, invocation-lineage, and data-lineage website.

    Args:
        spec_definition: Spec document for model and feature pages.
        plan: Existing plan for plan and data-lineage pages. Supply a plan built
            from the same spec document.
        features: Selected output features in the plan, or ``None`` for all features.
    """

    def __init__(
        self,
        spec_definition: spec.Spec,
        *,
        plan: execution_plan.ExecutionPlan,
        features: list[str] | None = None,
    ) -> None:
        self.spec = spec_definition
        self.plan = plan
        self.features = features

    def create_html(
        self,
        output_path: str | pathlib.Path | None = None,
        include_generated_at: bool = False,
    ) -> pathlib.Path:
        """Export the complete static website with navigation between its pages.

        The supplied plan is rendered without recompilation.
        Individual HTML report and subset feature-graph exports are not supported.

        Args:
            output_path: Index file; defaults to ``project_paths.EXPLORER_INDEX_FILE``.
                Section pages are written in spec, plan, and execution subdirectories;
                scripts and styles are written in js and css subdirectories.
            include_generated_at: Include a timestamp on the spec page.

        Returns:
            The path to the website index.
        """
        target = (
            pathlib.Path(output_path)
            if output_path is not None
            else project_paths.EXPLORER_INDEX_FILE
        )
        target = target.with_suffix(".html")
        plan = self.plan
        execution_scope = (
            "all features"
            if self.features is None
            else f"selected features: {', '.join(self.features)}"
        )
        feature_graph = spec.FeatureGraph(self.spec)
        context = spec_section._build_context(self.spec, include_generated_at)
        website = render.WebsiteContext(
            project_name=self.spec.name,
            index_filename=target.name,
            execution_scope=execution_scope,
            is_scoped=self.features is not None,
        )
        render.write_assets(target.parent)
        spec_section.SECTION.write_pages(
            target.parent,
            website,
            spec_section.build_context(context),
        )
        feature_lineage.SECTION.write_pages(
            target.parent,
            website,
            feature_lineage.build_context(feature_graph),
        )
        plan_section.SECTION.write_pages(
            target.parent,
            website,
            plan_section.build_context(plan, target.parent),
        )
        data_lineage.SECTION.write_pages(
            target.parent,
            website,
            data_lineage.build_context(self.spec, plan),
        )
        document = (
            render.html_environment()
            .get_template("index.html.j2")
            .render(
                spec_definition=self.spec,
                project_name=self.spec.name,
                summary=context.summary,
                invocation_count=len(plan.invocations),
                stage_count=len(plan.execution_stages),
                execution_scope=execution_scope,
                is_scoped=self.features is not None,
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
            "feature_graph.html",
            "js/feature_graph.js",
            "js/feature-graph.js",
            "js/lineage.js",
            "js/invocation_graph.js",
            "graph/feature_lineage.html",
            "graph/feature_graph.html",
            "graph/lineage.html",
            "spec/graph.html",
            "spec/lineage.html",
            "plan/graph.html",
        ):
            obsolete_page = target.parent / filename
            if obsolete_page != target:
                obsolete_page.unlink(missing_ok=True)
        return target
