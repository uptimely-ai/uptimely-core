"""Render Explorer pages with supplied or reusable execution plans."""

import pathlib

from uptimely import execution_plan, spec
from uptimely.explorer import explorer

from . import examples


def render_explorer(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
    *,
    plan: execution_plan.ExecutionPlan | None = None,
) -> pathlib.Path:
    """Render with a supplied or reusable plan, compiling only custom specs."""
    if plan is None:
        plan = examples.plan_for_spec(spec_definition)
    return explorer.Explorer(spec_definition, plan=plan).create_html(
        output_path, include_generated_at
    )
