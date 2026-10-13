"""Shared template loading for the documentation website."""

import jinja2


def html_environment() -> jinja2.Environment:
    """Load the centralized report templates and shared website layout.

    Returns:
        An HTML-autoescaping environment with access to the shared base template.
    """
    return jinja2.Environment(
        loader=jinja2.PackageLoader("uptimely", "templates"),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
    )
