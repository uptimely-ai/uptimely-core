"""Shared render-data filtering and template loading for the documentation website."""

import jinja2

WEBSITE_PAGES = {
    "spec": {
        section: f"spec/{section}.html"
        for section in ("overview", "features", "entities", "datasets", "dimensions", "functions")
    },
    "graph": {"lineage": "spec/graph.html"},
    "plan": {section: f"plan/{section}.html" for section in ("overview", "graph", "stages")},
    "execution": {"lineage": "execution/data_lineage.html"},
}


def filled_fields(**fields: object) -> dict[str, object]:
    """Return render fields without None values, preserving other falsy values."""
    return {key: value for key, value in fields.items() if value is not None}


def html_environment() -> jinja2.Environment:
    """Load the centralized report templates and shared website layout.

    Returns:
        An HTML-autoescaping environment with access to the shared base template.
    """
    environment = jinja2.Environment(
        loader=jinja2.PackageLoader("uptimely", "templates"),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
    )
    environment.globals["website_pages"] = WEBSITE_PAGES
    return environment
