"""Check template reuse without sharing project-specific render context."""

from uptimely.explorer import render


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
