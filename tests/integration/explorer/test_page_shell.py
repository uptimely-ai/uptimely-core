"""Verify shared branding and build context on every Explorer page."""

import pathlib
import re

import pytest
from support import examples as example_support

from uptimely import compiler, spec
from uptimely.explorer import explorer


@pytest.mark.parametrize("scoped", [False, True])
def test_pages_share_mobile_top_bar_and_desktop_sidebar_context(
    tmp_path: pathlib.Path,
    scoped: bool,
    example_bundle_factory: example_support.BundleFactory,
) -> None:
    features = ["health_signal_normalized"] if scoped else None
    bundle = example_bundle_factory(features=tuple(features) if features is not None else None)
    definition = bundle.spec_definition
    explorer.Explorer(definition, plan=bundle.execution_plan, features=features).create_html(
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
        assert "build-badge" not in bar
        root = "" if path.parent == tmp_path else "../"
        assert f'href="{root}custom.html"' in bar
        navigation = re.search(r"<nav\b.*?</nav>", document, re.DOTALL)
        assert navigation is not None
        nav = navigation.group()
        assert "openanalytics/explorer" not in nav
        assert f"<span>{definition.name}</span>" in nav
        assert f'href="{root}custom.html"' in nav
        assert 'data-lucide="house"' in nav
        badge = re.search(r'<span class="build-badge[^"]*"[^>]*>([^<]+)</span>', nav)
        assert badge is not None
        assert badge.group(1) == ("Partial build" if scoped else "Full build")
        assert nav.rfind('class="build-badge') > nav.rfind('class="site-subnav"')
        assert re.search(r"</span>\s*</nav>$", nav)
        assert ("build-badge-partial" in nav) == scoped
        assert "Spec: complete model" in nav
        assert ("selected features: health_signal_normalized" if scoped else "all features") in nav
        assert 'class="nav-label-toggle"' in nav
        assert 'aria-pressed="false" aria-controls="explorer-navigation"' in nav
        for attributes in re.findall(r"<a\b([^>]*)>", nav):
            assert "aria-label=" in attributes
            assert "title=" in attributes

    assert "grid-template-columns: max-content minmax(0, 1fr);" in styles
    assert "html.with-navigation .site-topbar { display: none; }" in styles
    assert ".site-nav { position: sticky; top: 0;" in styles
    assert ".site-nav.labels-hidden a span" in styles
    assert "--site-nav-width" not in styles
    assert re.search(
        r"\.build-badge \{[^}]*align-self: stretch;[^}]*"
        r"background: transparent; color: var\(--color-muted\);",
        styles,
    )


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
    assert 'window.matchMedia("(max-width: 640px)")' in script
    assert ".site-nav-context, .nav-label-toggle, .build-badge { display: none; }" in styles
    assert "margin-top: var(--site-topbar-height);" in graph_styles
    assert "height: calc(100dvh - var(--site-topbar-height));" in graph_styles


def test_desktop_navigation_labels_have_independent_toggle(tmp_path: pathlib.Path) -> None:
    definition = spec.Spec()
    explorer.Explorer(definition, plan=compiler.Compiler().compile(definition)).create_html(
        tmp_path / "index.html"
    )
    script = (tmp_path / "js/icons.js").read_text(encoding="utf-8")
    document = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert 'aria-label="Hide navigation labels"' in document
    assert 'data-lucide="panel-left-close"' in document
    assert 'data-lucide="panel-left-open"' in document
    heading = re.search(r'<div class="site-nav-heading">(.*?)</div>', document, re.DOTALL)
    assert heading is not None
    assert 'class="site-product"' in heading.group(1)
    assert 'class="nav-label-toggle"' in heading.group(1)
    assert "<span>Hide labels</span>" not in document
    assert 'navigation.classList.toggle("labels-hidden")' in script
    assert 'labelToggle.setAttribute("aria-pressed", String(labelsHidden))' in script
    assert '"Show navigation labels" : "Hide navigation labels"' in script


def test_context_panels_appear_on_catalog_and_lineage_pages(tmp_path: pathlib.Path) -> None:
    definition = spec.Spec()
    explorer.Explorer(definition, plan=compiler.Compiler().compile(definition)).create_html(
        tmp_path / "index.html"
    )
    lineage_pages = {
        "spec/feature-lineage.html": "node-details",
        "plan/invocation-lineage.html": "invocation-node-details",
    }
    catalog_pages = {
        "spec/features.html",
        "spec/entities.html",
        "spec/datasets.html",
        "spec/dimensions.html",
        "spec/functions.html",
        "plan/stages.html",
    }
    for path in tmp_path.rglob("*.html"):
        document = path.read_text(encoding="utf-8")
        filename = path.relative_to(tmp_path).as_posix()
        context = re.search(r'<aside class="site-context".*?</aside>', document, re.DOTALL)
        if filename == "execution/data-lineage.html":
            assert context is not None
            assert 'id="animation-context"' in context.group()
            assert 'aria-label="Animation context"' in context.group()
            assert 'aria-controls="animation-context"' in document
            assert '<h1 class="title-with-icon"' in context.group()
            continue
        if filename in catalog_pages:
            assert context is not None
            panel = context.group()
            section = path.stem
            assert 'id="catalog-context"' in panel
            assert f'aria-label="{section.title()} context"' in panel
            assert 'href="#catalog-overview"' in panel
            assert 'class="context-separator"' in panel
            assert 'class="nav-label-toggle context-label-toggle"' in panel
            assert 'aria-expanded="false" aria-controls="catalog-context"' in document
            assert 'src="../js/catalog_context.js"' in document
            assert 'id="lineage-context"' not in document
            continue
        if filename not in lineage_pages:
            assert context is None
            assert 'class="ui-button context-toggle"' not in document
            continue
        assert context is not None
        panel = context.group()
        assert 'id="lineage-context" aria-label="Lineage context"' in panel
        assert '<details class="panel" open>' in panel
        assert 'id="dataset-legend"' in panel
        assert f'id="{lineage_pages[filename]}"' in panel
        assert 'aria-live="polite"' in panel
        assert document.count('id="dataset-legend"') == 1
        assert document.count(f'id="{lineage_pages[filename]}"') == 1
        assert document.index("</nav>") < context.start() < document.index('class="site-content"')
        assert 'aria-expanded="false" aria-controls="lineage-context"' in document
        assert 'aria-label="Close lineage context"' in panel
        assert 'class="context-header"' in panel
        assert 'class="nav-label-toggle context-label-toggle"' in panel
        assert 'aria-label="Collapse lineage context"' in panel
        assert '<h1 class="title-with-icon"' in panel
        assert 'class="lineage-description"' not in panel
        assert 'class="lineage-control-groups"' in panel
        assert 'id="reset-lineage"' in panel
        assert panel.index("<h1") < panel.index('class="lineage-control-groups"')
        assert "lineage-toolbar" not in document

    base_styles = (tmp_path / "css/base.css").read_text(encoding="utf-8")
    script = (tmp_path / "js/icons.js").read_text(encoding="utf-8")
    controller = (tmp_path / "js/lineage_view_controller.js").read_text(encoding="utf-8")
    assert "grid-template-columns: max-content max-content minmax(0, 1fr);" in base_styles
    assert "min-height: var(--site-panel-header-height)" in base_styles
    assert ".site-context.is-collapsed { width: 67px; }" in base_styles
    assert 'contextPanel.classList.toggle("is-collapsed")' in script
    assert 'contextPanel.dataset.contextLabel || "lineage"' in script
    assert '`${collapsed ? "Expand" : "Collapse"} ${contextLabel} context`' in script
    assert ".site-context.is-open { display: flex; }" in base_styles
    assert "contextPanel.classList.toggle" in script
    assert "contextClose.focus()" in script
    assert "contextToggle.focus()" in script
    assert "details-2d" not in controller
    assert "observer.observe(document.getElementById('lineage'))" in controller


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
        navigation = re.search(r"<nav\b.*?</nav>", document, re.DOTALL)
        assert navigation is not None
        assert f"<span>{expected}</span>" in navigation.group()
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<p class="eyebrow">Project explorer</p>' in home
    assert "OpenAnalytics / Project explorer" not in home
