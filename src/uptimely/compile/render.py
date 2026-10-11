"""Render a compiled execution plan as a standalone HTML report."""

import json
import os
from pathlib import Path

from uptimely.analytics.render import GraphStyle
from uptimely.render import html_environment

from .compiler import ExecutionPlan

OUTPUT_PATH = Path("_generated") / "compile" / "execution_plan.html"


def _render_execution_plan(
    plan: ExecutionPlan,
    output_path: str | Path = OUTPUT_PATH,
    *,
    include_navigation: bool = False,
) -> Path:
    """Render an execution plan as an HTML report and return the written path.

    Args:
        plan: The compiled execution plan to render.
        output_path: Where to write the report file.
        include_navigation: Link to sibling documentation website pages.

    Returns:
        The path the report was written to.
    """
    plan_data = plan.to_dict()
    steps = plan_data["execution_order"]
    stages = plan_data["execution_stages"]
    target = Path(output_path)
    graph_nodes = [
        {
            "id": operation.id,
            "node_type": "callable",
            "operation_type": operation.kind,
            "callable_type": operation.kind,
            "label": f"{operation.function_id}({operation.entity_id})",
            "function_id": operation.function_id,
            "entity": operation.entity_id,
            "dataset_id": operation.dataset_id,
            "feature": operation.feature,
        }
        for operation in sorted(plan.operations, key=lambda operation: operation.id)
    ]
    graph_links = [
        {"source": dependency_id, "target": operation.id}
        for operation in plan.operations
        for dependency_id in operation.dependency_ids
    ]
    callable_graph_data = json.dumps(
        {
            "nodes": graph_nodes,
            "links": sorted(graph_links, key=lambda link: (link["source"], link["target"])),
        }
    ).replace("</script>", r"<\/script>")

    for stage in stages:
        stage["steps"].sort(
            key=lambda step: (
                step["entrypoint"],
                step["entity"],
                step["dataset"] or "",
                step["feature"] or "",
            )
        )
        for step in stage["steps"]:
            step["depends_on_callables"].sort(key=lambda dependency: dependency["function"])
            entrypoint = step["entrypoint"]
            source_path = entrypoint.partition(":")[0] if entrypoint else None
            if source_path and not source_path.endswith(".py"):
                source_path = source_path.replace(".", "/") + ".py"
            step["source_href"] = (
                Path(os.path.relpath(source_path, start=target.parent)).as_posix()
                if source_path
                else None
            )

    environment = html_environment()
    document = environment.get_template("plan/index.html.j2").render(
        spec_path=plan_data["spec_path"],
        spec_version=plan_data["spec_version"],
        callable_count=plan_data["callable_count"],
        function_count=len({step["function"] for step in steps}),
        entity_count=len({operation.entity_id for operation in plan.execution_order}),
        feature_count=len({operation.feature for operation in plan.execution_order}),
        stages=stages,
        callable_graph_data=callable_graph_data,
        graph_style=GraphStyle(),
        include_navigation=include_navigation,
        active_page="plan",
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target
