"""Shared template loading for standalone reports and the documentation website."""

from jinja2 import ChoiceLoader, Environment, PackageLoader, select_autoescape


def html_environment(template_directory: str) -> Environment:
    """Load a report's templates together with the shared website layout.

    Args:
        template_directory: Package-relative directory containing the report templates.

    Returns:
        An HTML-autoescaping environment with access to the shared base template.
    """
    return Environment(
        loader=ChoiceLoader(
            [
                PackageLoader("uptimely", template_directory),
                PackageLoader("uptimely", "docs/templates"),
            ]
        ),
        autoescape=select_autoescape(["html", "j2"]),
    )
