"""Verify shared branding and build context on every Explorer page."""

import pathlib
import re

import pytest
from conftest import EXAMPLES_ROOT, example_bundle

from uptimely import compiler, spec
from uptimely.explorer import explorer


@pytest.mark.parametrize("scoped", [False, True])
def test_pages_share_minimal_top_bar_and_build_badge(tmp_path: pathlib.Path, scoped: bool) -> None:
    definition = spec.load_spec(EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json")
    features = ["health_signal_normalized"] if scoped else None
    plan = example_bundle(features=tuple(features) if features is not None else None).execution_plan
    explorer.Explorer(definition, plan=plan, features=features).create_html(
        tmp_path / "custom.html"
    )
    documents = list(tmp_path.rglob("*.html"))
    assert len(documents) == 12
    styles = (tmp_path / "css/base.css").read_text(encoding="utf-8")
    assert re.search(
        r"\.site-product \{[^}]*display: grid;[^}]*"
        r"grid-template-columns: 16px minmax\(0, 1fr\);",
        styles,
    )
    for path in documents:
        document = path.read_text(encoding="utf-8")
        bars = re.findall(r'<header class="site-topbar".*?</header>', document, re.DOTALL)
        assert len(bars) == 1
        bar = bars[0]
        assert f"<span>{definition.name}</span>" in bar
        assert "OpenAnalytics" not in bar
        assert "icon--home" in bar
        assert 'data-lucide="house"' in bar
        assert re.search(
            r'<a class="site-product"[^>]*><i\b[^>]*></i><span>',
            bar,
        )
        assert "site-versions" not in bar
        assert "site-section" not in bar
        assert "Uptimely Core version" not in bar
        assert "<dl" not in bar
        assert "<details" not in bar
        badge = re.search(r'<span class="build-badge[^"]*"[^>]*>([^<]+)</span>', bar)
        assert badge is not None
        assert badge.group(1) == ("Partial build" if scoped else "Full build")
        assert ("build-badge-partial" in bar) == scoped
        assert "Spec: complete model" in bar
        assert ("selected features: health_signal_normalized" if scoped else "all features") in bar
        root = "" if path.parent == tmp_path else "../"
        assert f'href="{root}custom.html"' in bar
        navigation = re.search(r"<nav\b.*?</nav>", document, re.DOTALL)
        assert navigation is not None
        assert "openanalytics/explorer" not in navigation.group()
        assert "icon--home" not in navigation.group()


def test_mobile_navigation_uses_collapsible_menu(tmp_path: pathlib.Path) -> None:
    definition = spec.Spec()
    explorer.Explorer(definition, plan=compiler.Compiler().compile(definition)).create_html(
        tmp_path / "index.html"
    )
    styles = (tmp_path / "css/base.css").read_text(encoding="utf-8")
    graph_styles = (tmp_path / "css/graph.css").read_text(encoding="utf-8")
    script = (tmp_path / "js/icons.js").read_text(encoding="utf-8")
    document = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert 'class="mobile-nav-toggle"' in document
    assert 'data-lucide="menu"' in document
    assert 'aria-expanded="false" aria-controls="explorer-navigation"' in document
    assert 'id="explorer-navigation"' in document
    assert "display: none;" in styles
    assert ".site-nav.is-open" in styles
    assert "max-height: calc(100dvh - var(--site-topbar-height));" in styles
    assert "navigationToggle.focus();" in script
    assert "inset: var(--site-topbar-height) 0 0;" in graph_styles


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (None, "Untitled analytics project"),
        ("", "Untitled analytics project"),
        ("<Project> & analytics", "&lt;Project&gt; &amp; analytics"),
    ],
)
def test_top_bar_project_name_is_escaped_with_untitled_fallback(
    tmp_path: pathlib.Path, name: str | None, expected: str
) -> None:
    definition = spec.Spec(name=name)
    plan = compiler.Compiler().compile(definition)
    explorer.Explorer(definition, plan=plan).create_html(tmp_path / "index.html")
    for path in tmp_path.rglob("*.html"):
        document = path.read_text(encoding="utf-8")
        bar = re.search(r'<header class="site-topbar".*?</header>', document, re.DOTALL)
        assert bar is not None
        assert f"<span>{expected}</span>" in bar.group()
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<p class="eyebrow">Project explorer</p>' in home
    assert "OpenAnalytics / Project explorer" not in home
