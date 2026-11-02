import { renderCatalog } from "./catalogs.js";
import { animation } from "./animation.js";
import { dashboard, lineage, planOverview, specOverview } from "./views.js";
import { shell } from "./ui.js";

const FORMAT_VERSION = 1;
const CATALOG_VIEWS = new Set(["features", "entities", "datasets", "dimensions", "functions", "stages"]);
const VIEWS = new Set(["home", "spec", "plan", "lineage", "topology", "animation", ...CATALOG_VIEWS]);
const LEGACY_ROUTES = {
  overview: "home", catalogs: "features", "feature-lineage": "lineage",
  "invocation-lineage": "topology", plan: "stages", animation: "animation",
};

function followLegacyRoute() {
  const legacyView = LEGACY_ROUTES[location.hash.slice(1)];
  if (!legacyView) return;
  const url = new URL(location.href);
  url.searchParams.set("view", legacyView);
  url.hash = "";
  location.replace(url.href);
}

function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Unable to load Explorer library: ${url}. Check your network connection and reload.`));
    document.head.append(script);
  });
}

function loadStylesheet(url) {
  return new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    link.onload = resolve;
    link.onerror = () => reject(new Error(`Unable to load Explorer stylesheet: ${url}. Reload this page.`));
    document.head.append(link);
  });
}

async function loadExplorerData() {
  const configuration = window.UTIMELY_EXPLORER_CONFIG;
  if (!configuration || typeof configuration.dataUrl !== "string") {
    throw new Error("Explorer data URL is not configured.");
  }
  const response = await fetch(configuration.dataUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load Explorer data (HTTP ${response.status}). Build the project with "uptimely project build" and refresh this page.`);
  }
  const data = await response.json();
  if (!data || data.format_version !== FORMAT_VERSION || !data.project || !data.scope || !data.catalogs
      || !data.graphs || !data.plan || !Array.isArray(data.stages) || !Array.isArray(data.animation?.stages)) {
    throw new Error('Explorer data is missing or uses an unsupported format. Rebuild with "uptimely project build".');
  }
  return data;
}

async function initialize() {
  followLegacyRoute();
  window.addEventListener("hashchange", followLegacyRoute);
  const view = new URLSearchParams(location.search).get("view") || "home";
  if (!VIEWS.has(view)) throw new Error(`Unknown Explorer page: ${view}. Use the project home page to navigate.`);
  const stylesheet = view === "home" ? "dashboard" : view === "animation" ? "data_lineage"
    : view === "lineage" || view === "topology" ? "graph" : "spec";
  const [data] = await Promise.all([loadExplorerData(), loadStylesheet(`./css/${stylesheet}.css`)]);
  let context = "", content;
  if (CATALOG_VIEWS.has(view)) {
    ({ context, content } = renderCatalog(data, view));
  } else if (view === "lineage" || view === "topology") {
    ({ context, content } = lineage(data, view === "topology"));
  } else if (view === "animation") {
    ({ context, content } = animation(data));
  } else {
    content = view === "spec" ? specOverview(data) : view === "plan" ? planOverview(data) : dashboard(data);
  }
  document.title = `${view === "home" ? data.project.name || "Analytics project" : view[0].toUpperCase() + view.slice(1)} | Explorer`;
  document.body.className = CATALOG_VIEWS.has(view) ? "catalog-context-page" : "";
  if (view === "lineage" || view === "topology") document.body.classList.add("lineage-page");
  document.body.innerHTML = shell(data, view, context, content);
  if (CATALOG_VIEWS.has(view)) await import("./catalog_context.js");
  if (view === "lineage" || view === "topology") {
    const style = view === "topology" ? data.graphs.invocation_style : data.graphs.feature_style;
    document.body.style.setProperty("--lineage-background", style.background_color);
    document.getElementById("action-legend")?.style.setProperty("--color", style.function_color);
    await loadScript("https://unpkg.com/force-graph@1.52.0/dist/force-graph.min.js");
    await loadScript("https://unpkg.com/three@0.160.0/build/three.min.js");
    await loadScript("https://unpkg.com/3d-force-graph@1.77.0/dist/3d-force-graph.min.js");
    await loadScript("https://unpkg.com/three-spritetext@1.10.0/dist/three-spritetext.min.js");
    if (view === "topology") await import("./invocation_lineage.js");
    else await import("./feature_lineage.js");
  }
  await loadScript("https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js");
  await import("./icons.js");
  if (view === "animation") await import("./data_lineage.js");
  if (view === "functions") {
    await loadStylesheet("https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/monokai-sublime.min.css");
    await loadScript("https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js");
    await import("./code_highlight.js");
  }
}

try {
  await initialize();
} catch (error) {
  console.error("Unable to initialize Explorer", error);
  const loadStatus = document.getElementById("load-status");
  if (loadStatus) loadStatus.hidden = true;
  let errorStatus = document.getElementById("error-status");
  if (!errorStatus) {
    errorStatus = document.createElement("div");
    errorStatus.id = "error-status";
    errorStatus.className = "explorer-error";
    errorStatus.setAttribute("role", "alert");
    (document.getElementById("content") || document.body).prepend(errorStatus);
  }
  errorStatus.hidden = false;
  errorStatus.textContent = error.message;
}
