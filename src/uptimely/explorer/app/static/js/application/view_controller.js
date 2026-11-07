import { renderCatalog } from "../catalogs/catalog_renderer.js";
import { animation } from "../animation/animation_renderer.js";
import { dashboard, lineage, planOverview } from "../rendering/page_renderer.js";
import { shell } from "../rendering/shared_markup.js";
import { initializeCatalog } from "../catalogs/catalog_navigation.js";
import { initializeIcons } from "../navigation/sidebar_controls.js";
import { initializeFeatureLineage } from "../lineage/feature_lineage.js";
import { initializeInvocationLineage } from "../lineage/invocation_lineage.js";
import { initializeDataLineage } from "../animation/playback_controller.js";
import { initializeHighlighting } from "../catalogs/function_highlighting.js";
import {
  infoPage, initializeLogs, initializePreview, loadInfo, loadLogs, loadPreviews, logsPage,
  previewPage,
} from "../engine_pages.js";

const INITIALIZERS = {
  catalog: initializeCatalog, icons: initializeIcons,
  lineage: initializeFeatureLineage, topology: initializeInvocationLineage,
  animation: initializeDataLineage, highlight: initializeHighlighting,
};
const initializer = (name, component = false) => ({ name, component });
const icons = [initializer("icons")];
const catalog = (name, highlight = false) => ({
  stylesheet: "spec", catalog: true, highlight,
  initialize: [initializer("catalog", true), ...icons,
    ...(highlight ? [initializer("highlight")] : [])],
  render: data => renderCatalog(data, name),
});
const content = render => data => ({ context: "", content: render(data) });
const VIEWS = {
  home: { stylesheet: "dashboard", initialize: icons, render: content(dashboard) },
  plan: { stylesheet: "spec", initialize: icons, render: content(planOverview) },
  features: catalog("features"),
  profiles: catalog("profiles", true),
  dimensions: catalog("dimensions"),
  functions: catalog("functions", true),
  stages: catalog("stages"),
  lineage: {
    stylesheet: "lineage", lineageStyle: "feature_style",
    initialize: [initializer("lineage", true), ...icons],
    render: data => lineage(data, false),
  },
  topology: {
    stylesheet: "lineage", lineageStyle: "invocation_style",
    initialize: [initializer("topology"), ...icons],
    render: data => lineage(data, true),
  },
  animation: {
    stylesheet: "data_lineage",
    initialize: [...icons, initializer("animation", true)],
    render: animation,
  },
  info: {
    stylesheet: "engine", engine: true, initialize: icons, load: loadInfo,
    render: (data, runData) => infoPage(runData, data.stages),
  },
  logs: {
    stylesheet: "engine", engine: true, initialize: icons, load: loadLogs,
    initializePage: initializeLogs,
    render: (data, runData) => logsPage(runData),
  },
  preview: {
    stylesheet: "engine", engine: true, initialize: icons, load: loadPreviews,
    initializePage: initializePreview,
    render: (data, runData) => previewPage(data, runData),
  },
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
    body.className = [view.catalog && "catalog-context-page", view.engine && "engine-page"]
      .filter(Boolean).join(" ");
    body.style.removeProperty("--lineage-background");
    if (view.lineageStyle) body.classList.add("lineage-page");
    body.innerHTML = shell(this.data, name, context, content);
  }

  initializeView(view, sidebars) {
    const { signal } = this.controller;
    if (view.lineageStyle) {
      const style = this.data.graphs[view.lineageStyle];
      this.document.body.style.setProperty("--lineage-background", style.background_color);
      this.document.getElementById("operator-legend")?.style.setProperty("--color", style.function_color);
    }
    for (const step of view.initialize) {
      const component = this.initializers[step.name](signal);
      if (step.component) this.component = component;
    }
    this.restoreSidebars(sidebars);
  }

  focusHeading() {
    this.browser.scrollTo({ top: 0, left: 0, behavior: "instant" });
    const heading = this.document.querySelector("main h1, .site-context h1, main");
    heading?.setAttribute("tabindex", "-1");
    heading?.focus({ preventScroll: true });
  }

  mount(name, view, activateStyles, pageData) {
    const markup = view.render(this.data, pageData);
    const sidebars = this.sidebarState();
    this.dispose();
    this.controller = new AbortController();
    try {
      activateStyles();
      this.renderShell(name, view, markup);
      this.initializeView(view, sidebars);
      view.initializePage?.(this.browser, this.controller.signal);
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
