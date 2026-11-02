import { renderCatalog } from "../catalogs/catalog_renderer.js";
import { animation } from "../animation/animation_renderer.js";
import { dashboard, lineage, planOverview, specOverview } from "../rendering/page_renderer.js";
import { shell } from "../rendering/shared_markup.js";
import { initializeCatalog } from "../catalogs/catalog_navigation.js";
import { initializeIcons } from "../navigation/sidebar_controls.js";
import { initializeFeatureLineage } from "../graphs/feature_graph.js";
import { initializeInvocationLineage } from "../graphs/invocation_graph.js";
import { initializeDataLineage } from "../animation/playback_controller.js";
import { initializeHighlighting } from "../catalogs/function_highlighting.js";

const INITIALIZERS = {
  catalog: initializeCatalog, icons: initializeIcons,
  lineage: initializeFeatureLineage, topology: initializeInvocationLineage,
  animation: initializeDataLineage, highlight: initializeHighlighting,
};
const catalog = name => ({
  stylesheet: "spec", catalog: true, render: data => renderCatalog(data, name),
});
const content = render => data => ({ context: "", content: render(data) });
const VIEWS = {
  home: { stylesheet: "dashboard", render: content(dashboard) },
  spec: { stylesheet: "spec", render: content(specOverview) },
  plan: { stylesheet: "spec", render: content(planOverview) },
  features: catalog("features"),
  entities: catalog("entities"),
  datasets: catalog("datasets"),
  dimensions: catalog("dimensions"),
  functions: { ...catalog("functions"), highlight: true },
  stages: catalog("stages"),
  lineage: { stylesheet: "graph", graph: "feature_style", render: data => lineage(data, false) },
  topology: { stylesheet: "graph", graph: "invocation_style", render: data => lineage(data, true) },
  animation: { stylesheet: "data_lineage", render: animation },
};

export function getView(name) {
  if (!Object.hasOwn(VIEWS, name)) {
    throw new Error(`Unknown Explorer page: ${name}. Use the project home page to navigate.`);
  }
  return VIEWS[name];
}

export class ViewController {
  constructor(browser, data, initializers = INITIALIZERS) {
    this.browser = browser;
    this.document = browser.document;
    this.data = data;
    this.initializers = initializers;
    this.activeView = null;
    this.controller = null;
    this.component = null;
  }

  sidebarState() {
    return {
      labelsHidden: this.document.getElementById("explorer-navigation")?.classList.contains("labels-hidden"),
      contextCollapsed: this.document.querySelector(".site-context")?.classList.contains("is-collapsed"),
    };
  }

  restoreSidebars({ labelsHidden, contextCollapsed }) {
    if (labelsHidden) this.document.querySelector(".site-nav .nav-label-toggle").click();
    if (contextCollapsed) this.document.querySelector(".context-label-toggle")?.click();
  }

  renderShell(name, view, { context, content }) {
    this.document.title = `${name === "home" ? this.data.project.name || "Analytics project" : name[0].toUpperCase() + name.slice(1)} | Explorer`;
    const { body } = this.document;
    body.className = view.catalog ? "catalog-context-page" : "";
    body.style.removeProperty("--lineage-background");
    if (view.graph) body.classList.add("lineage-page");
    body.innerHTML = shell(this.data, name, context, content);
  }

  initializeComponents(name, view, sidebars) {
    const { signal } = this.controller;
    const initialize = this.initializers;
    if (view.catalog) this.component = initialize.catalog(signal);
    if (view.graph) {
      const style = this.data.graphs[view.graph];
      this.document.body.style.setProperty("--lineage-background", style.background_color);
      this.document.getElementById("action-legend")?.style.setProperty("--color", style.function_color);
      initialize[name](signal);
    }
    initialize.icons(signal);
    this.restoreSidebars(sidebars);
    if (name === "animation") this.component = initialize.animation(signal);
    if (view.highlight) initialize.highlight();
  }

  focusHeading() {
    this.browser.scrollTo({ top: 0, left: 0, behavior: "instant" });
    const heading = this.document.querySelector("main h1, .site-context h1, main");
    heading?.setAttribute("tabindex", "-1");
    heading?.focus({ preventScroll: true });
  }

  mount(name, view, activateStyles) {
    const markup = view.render(this.data);
    const sidebars = this.sidebarState();
    this.dispose();
    this.controller = new AbortController();
    try {
      activateStyles();
      this.renderShell(name, view, markup);
      this.initializeComponents(name, view, sidebars);
      this.activeView = name;
      this.focusHeading();
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  update() {
    this.document.getElementById("error-status")?.remove();
    this.component?.update();
  }

  dispose() {
    this.controller?.abort();
    this.controller = null;
    this.component = null;
    this.activeView = null;
  }
}
