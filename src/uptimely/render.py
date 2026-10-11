"""Shared template loading for standalone reports and the documentation website."""

from jinja2 import Environment, PackageLoader, select_autoescape


def html_environment() -> Environment:
    """Load the centralized report templates and shared website layout.

    Returns:
        An HTML-autoescaping environment with access to the shared base template.
    """
    return Environment(
        loader=PackageLoader("uptimely", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
    )
