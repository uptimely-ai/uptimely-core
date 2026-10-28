"""Shared render-data filtering and template loading for the Explorer website."""

import dataclasses
import functools
import importlib.resources
import pathlib
from collections import abc

import jinja2

from uptimely import project_paths

ASSET_DIRECTORIES = ("css", "js")

WEBSITE_PAGES = {
    "spec": {
        **{
            section: f"spec/{section}.html"
            for section in (
                "overview",
                "features",
                "entities",
                "datasets",
                "dimensions",
                "functions",
            )
        },
        "feature_lineage": "spec/feature_lineage.html",
    },
    "plan": {
        section: f"plan/{section}.html" for section in ("overview", "invocation_lineage", "stages")
    },
    "execution": {"data_lineage": "execution/data_lineage.html"},
}


@dataclasses.dataclass(frozen=True)
class WebsiteContext:
    """Navigation and build information shared by website sections."""

    project_name: str | None = None
    index_filename: str = project_paths.EXPLORER_INDEX_FILE.name
    execution_scope: str = "all features"
    is_scoped: bool = False
    root_path: str = "../"


@dataclasses.dataclass(frozen=True)
class WebsitePage:
    """Template, destination, and navigation identity of a section page."""

    template: str
    filename: str
    active_section: str | None = None
    title: str | None = None


@dataclasses.dataclass(frozen=True)
class WebsiteSection:
    """Render section data with shared website context and write its pages."""

    active_page: str
    pages: tuple[WebsitePage, ...]

    def render_page(
        self,
        page: WebsitePage,
        website: WebsiteContext,
        data: abc.Mapping[str, object],
    ) -> str:
        """Render a page with consistent navigation and build-scope context."""
        context = {
            **data,
            **dataclasses.asdict(website),
            "include_navigation": True,
            "active_page": self.active_page,
        }
        if page.active_section is not None:
            context["active_section"] = page.active_section
        if page.title is not None:
            context["section_title"] = page.title
        return html_environment().get_template(page.template).render(context)

    def write_pages(
        self,
        output_directory: pathlib.Path,
        website: WebsiteContext,
        data: abc.Mapping[str, object],
    ) -> None:
        """Render and write each section page, propagating rendering and I/O errors."""
        for page in self.pages:
            document = self.render_page(page, website, data)
            target = output_directory / page.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(document, encoding="utf-8")


def filled_fields(**fields: object) -> dict[str, object]:
    """Return render fields without None values, preserving other falsy values."""
    return {key: value for key, value in fields.items() if value is not None}


@functools.cache
def html_environment() -> jinja2.Environment:
    """Load the Explorer templates and shared website layout.

    Returns:
        A shared HTML-autoescaping environment that caches compiled templates.
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
