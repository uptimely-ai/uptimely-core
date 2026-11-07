const LEGACY_ROUTES = {
  catalogs: "features", "feature-lineage": "lineage",
  "invocation-lineage": "topology", plan: "stages", animation: "animation",
};

export class Router {
  constructor(browser, onNavigate) {
    this.browser = browser;
    this.onNavigate = onNavigate;
    this.controller = new AbortController();
  }

  currentView() {
    const url = new URL(this.browser.location.href);
    const hash = url.hash.slice(1);
    const legacyView = Object.hasOwn(LEGACY_ROUTES, hash) ? LEGACY_ROUTES[hash] : null;
    if (legacyView) {
      url.searchParams.set("view", legacyView);
      url.hash = "";
      this.browser.history.replaceState(null, "", url);
    }
    if (url.searchParams.get("view") === "spec") {
      url.searchParams.set("view", "features");
      url.hash = "";
      this.browser.history.replaceState(null, "", url);
    }
    return url.searchParams.get("view") || "home";
  }

  internalLink(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
    const link = event.target.closest("a[href]");
    if (!link || link.hasAttribute("download") || link.target && link.target !== "_self") return null;
    if (link.getAttribute("href").startsWith("#")) return null;
    const url = new URL(link.href, this.browser.location.href);
    const current = new URL(this.browser.location.href);
    return url.origin === current.origin && url.pathname === current.pathname ? url : null;
  }

  start() {
    const { signal } = this.controller;
    this.browser.document.addEventListener("click", event => {
      const url = this.internalLink(event);
      if (!url) return;
      event.preventDefault();
      if (url.href !== this.browser.location.href) this.browser.history.pushState(null, "", url);
      void this.onNavigate();
    }, { signal });
    for (const type of ["popstate", "hashchange"]) {
      this.browser.addEventListener(type, () => { void this.onNavigate(); }, { signal });
    }
  }

  dispose() {
    this.controller.abort();
  }
}
