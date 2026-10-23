"""Shared render-data filtering and template loading for the Explorer website."""

import importlib.resources
import pathlib

import jinja2

ASSET_DIRECTORIES = ("css", "js")

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
    """Load the Explorer templates and shared website layout.

    Returns:
        An HTML-autoescaping environment with access to the shared base template.
    """
    environment = jinja2.Environment(
        loader=jinja2.PackageLoader("uptimely.explorer.app", "templates"),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
    )
    environment.globals["website_pages"] = WEBSITE_PAGES
    return environment


def write_assets(output_directory: pathlib.Path) -> None:
    """Write the packaged scripts and styles alongside the Explorer pages.

    Args:
        output_directory: Root of the generated Explorer website.
    """
    app = importlib.resources.files("uptimely.explorer").joinpath("app")
    environment = html_environment().overlay(autoescape=False)
    for directory in ASSET_DIRECTORIES:
        target_directory = output_directory / directory
        target_directory.mkdir(parents=True, exist_ok=True)
        for resource in sorted(app.joinpath(directory).iterdir(), key=lambda item: item.name):
            content = resource.read_text(encoding="utf-8")
            filename = resource.name
            if filename.endswith(".j2"):
                content = environment.from_string(content).render()
                filename = filename.removesuffix(".j2")
            (target_directory / filename).write_text(content, encoding="utf-8")
