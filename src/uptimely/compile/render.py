"""Render a compiled execution plan as a standalone HTML report."""

import json
import os
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from uptimely.analytics.render import GraphStyle

from .compiler import ExecutionPlan

OUTPUT_PATH = Path("generated") / "compile" / "execution_plan.html"


def _render_execution_plan(plan: ExecutionPlan, output_path: str | Path = OUTPUT_PATH) -> Path:
    """Render an execution plan as an HTML report and return the written path.

    Args:
        plan: The compiled execution plan to render.
        output_path: Where to write the report file.

    Returns:
        The path the report was written to.
    """
    plan_data = plan.to_dict()
    steps = plan_data["execution_order"]
    stages = plan_data["execution_stages"]
    target = Path(output_path)
    graph_nodes = [
        {
            "node_type": "callable",
            "operation_type": operation.kind,
            "callable_type": operation.kind,
            "label": f"{operation.function_id}({operation.entity_id})",
            "function_id": operation.function_id,
            "entity": operation.entity_id,
            "dataset_id": operation.dataset_id,
            "feature": operation.feature,
        }
        for operation in plan.execution_order
    ]
    graph_links = [
        {"source": dependency_id, "target": operation.id}
        for operation in plan.operations
        for dependency_id in operation.dependency_ids
    ]
    callable_graph_data = json.dumps(
        {
            "nodes": graph_nodes,
            "links": graph_links,
        }
    ).replace("</script>", r"<\/script>")

    for stage in stages:
        for step in stage["steps"]:
            entrypoint = step["entrypoint"]
            source_path = entrypoint.partition(":")[0] if entrypoint else None
            if source_path and not source_path.endswith(".py"):
                source_path = source_path.replace(".", "/") + ".py"
            step["source_href"] = (
                Path(os.path.relpath(source_path, start=target.parent)).as_posix()
                if source_path
                else None
            )

    environment = Environment(
        loader=PackageLoader("uptimely", "compile/templates"),
        autoescape=select_autoescape(["html"]),
    )
    document = environment.get_template("report.html.j2").render(
        spec_path=plan_data["spec_path"],
        spec_version=plan_data["spec_version"],
        callable_count=plan_data["callable_count"],
        function_count=len({step["function"] for step in steps}),
        entity_count=len({operation.entity_id for operation in plan.execution_order}),
        feature_count=len({operation.feature for operation in plan.execution_order}),
        stages=stages,
        callable_graph_data=callable_graph_data,
        graph_style=GraphStyle(),
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target
