"""Check template reuse without sharing project-specific render context."""

import pathlib

import jinja2
import pytest

from uptimely.explorer import render, sections


def test_html_environment_reuses_compiled_templates() -> None:
    first = render.html_environment()
    second = render.html_environment()

    assert first is second
    assert first.get_template("index.html.j2") is second.get_template("index.html.j2")


def test_shared_environment_keeps_render_context_isolated_and_escaped() -> None:
    environment = render.html_environment()
    template = environment.from_string("{{ project_name }}")

    assert template.render(project_name="<First project>") == "&lt;First project&gt;"
    assert template.render(project_name="Second project") == "Second project"
    assert template.render() == ""


def test_website_section_writes_pages_with_shared_navigation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = jinja2.Environment(
        loader=jinja2.DictLoader(
            {
                "page.html.j2": (
                    "{{ project_name }}|{{ index_filename }}|{{ execution_scope }}|"
                    "{{ is_scoped }}|{{ root_path }}|{{ include_navigation }}|"
                    "{{ active_page }}|{{ active_section }}|{{ section_title }}|{{ content }}"
                ),
            }
        ),
        autoescape=True,
    )
    monkeypatch.setattr(render, "html_environment", lambda: environment)
    section = render.WebsiteSection(
        active_page="plan",
        pages=(
            render.WebsitePage("page.html.j2", "plan/overview.html", "overview", "Overview"),
            render.WebsitePage("page.html.j2", "plan/stages.html", "stages", "Stages"),
        ),
    )
    section.write_pages(
        tmp_path,
        render.WebsiteContext(
            project_name="<Project>",
            index_filename="custom.html",
            execution_scope="selected features: result",
            is_scoped=True,
        ),
        {"content": "<data>", "active_page": "wrong", "project_name": "wrong"},
    )

    for name in ("overview", "stages"):
        assert (tmp_path / f"plan/{name}.html").read_text(encoding="utf-8") == (
            "&lt;Project&gt;|custom.html|selected features: result|True|../|True|"
            f"plan|{name}|{name.title()}|&lt;data&gt;"
        )
    assert environment.globals.get("project_name") is None


def test_website_section_does_not_leak_context_between_renders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = jinja2.Environment(
        loader=jinja2.DictLoader(
            {"test.html": "{{ project_name }}|{{ content }}|{{ active_section }}"}
        ),
        autoescape=True,
    )
    monkeypatch.setattr(render, "html_environment", lambda: environment)
    page = render.WebsitePage("test.html", "index.html")
    section = render.WebsiteSection("home", (page,))
    assert (
        section.render_page(
            page, render.WebsiteContext(project_name="First"), {"content": "first data"}
        )
        == "First|first data|"
    )
    assert section.render_page(page, render.WebsiteContext(project_name="Second"), {}) == "Second||"


def test_website_section_propagates_template_errors(tmp_path: pathlib.Path) -> None:
    section = render.WebsiteSection(
        "home", (render.WebsitePage("missing-template.html.j2", "nested/index.html"),)
    )

    with pytest.raises(jinja2.TemplateNotFound):
        section.write_pages(tmp_path, render.WebsiteContext(), {})
    assert not (tmp_path / "nested").exists()


def test_website_section_propagates_write_errors(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = jinja2.Environment(loader=jinja2.DictLoader({"test.html": "content"}))
    monkeypatch.setattr(render, "html_environment", lambda: environment)
    section = render.WebsiteSection("home", (render.WebsitePage("test.html", "index.html"),))
    (tmp_path / "index.html").mkdir()

    with pytest.raises(IsADirectoryError):
        section.write_pages(tmp_path, render.WebsiteContext(), {})


def test_sections_are_modules_instead_of_single_file_packages() -> None:
    for name in sections.__all__:
        module = getattr(sections, name)
        assert pathlib.Path(module.__file__).name == f"{name}.py"
