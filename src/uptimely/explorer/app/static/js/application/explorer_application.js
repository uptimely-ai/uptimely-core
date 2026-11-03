import { AssetLoader } from "./asset_loader.js";
import { Router } from "./history_router.js";
import { getView, ViewController } from "./view_controller.js";

const FORMAT_VERSION = 1;

export async function loadExplorerData(configuration, fetchData) {
  if (!configuration || typeof configuration.dataUrl !== "string") {
    throw new Error("Explorer data URL is not configured.");
  }
  const response = await fetchData(configuration.dataUrl, { cache: "no-store" });
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

export class Explorer {
  constructor(browser, initializers) {
    this.browser = browser;
    this.assets = new AssetLoader(browser.document);
    this.router = new Router(browser, () => this.navigate());
    this.initializers = initializers;
    this.views = null;
    this.navigation = 0;
  }

  async start() {
    const version = ++this.navigation;
    try {
      getView(this.router.currentView());
      const data = await loadExplorerData(
        this.browser.UTIMELY_EXPLORER_CONFIG, this.browser.fetch.bind(this.browser),
      );
      if (version !== this.navigation) return;
      this.views = new ViewController(this.browser, data, this.initializers);
      this.router.start();
      await this.navigate();
    } catch (error) {
      if (version === this.navigation) this.showError(error);
    }
  }

  async navigate() {
    const version = ++this.navigation;
    try {
      const name = this.router.currentView();
      const view = getView(name);
      if (name === this.views.activeView) {
        this.views.update();
        return;
      }
      const stylesheets = await this.assets.prepare(view);
      // Ignore dependencies that finish after a newer navigation request.
      if (version !== this.navigation) return;
      const pageData = view.load ? await view.load(
        this.browser.fetch.bind(this.browser), this.browser.UTIMELY_EXPLORER_CONFIG,
      ) : null;
      if (version !== this.navigation) return;
      this.views.mount(name, view, () => this.assets.activate(stylesheets), pageData);
    } catch (error) {
      if (version === this.navigation) this.showError(error);
    }
  }

  showError(error) {
    this.browser.console.error("Unable to display Explorer", error);
    const { document } = this.browser;
    const loading = document.getElementById("load-status");
    if (loading) loading.hidden = true;
    let status = document.getElementById("error-status");
    if (!status) {
      status = document.createElement("div");
      status.id = "error-status";
      status.className = "explorer-error";
      status.setAttribute("role", "alert");
      (document.getElementById("content") || document.body).prepend(status);
    }
    status.hidden = false;
    status.textContent = error.message;
  }

  dispose() {
    this.navigation++;
    this.router.dispose();
    this.views?.dispose();
  }
}
