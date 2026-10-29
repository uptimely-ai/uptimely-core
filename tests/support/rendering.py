"""Render Explorer pages using explicitly supplied execution plans."""

import pathlib

from uptimely import execution_plan, spec
from uptimely.explorer import explorer


def render_explorer(
    spec_definition: spec.Spec,
    output_path: str | pathlib.Path | None = None,
    include_generated_at: bool = False,
    *,
    plan: execution_plan.ExecutionPlan,
) -> pathlib.Path:
    """Render a supplied plan without compiling or loading example artifacts."""
    return explorer.Explorer(spec_definition, plan=plan).create_html(
        output_path, include_generated_at
    )
