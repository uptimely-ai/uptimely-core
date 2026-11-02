class BrowserHistory {
  constructor(url, emit) {
    this.entries = [url];
    this.position = 0;
    this.emit = emit;
  }

  get location() {
    return new URL(this.entries[this.position]);
  }

  pushState(_state, _title, value) {
    const url = new URL(value, this.location);
    this.entries.splice(++this.position, this.entries.length, url.href);
  }

  replaceState(_state, _title, value) {
    this.entries[this.position] = new URL(value, this.location).href;
  }

  move(delta) {
    this.position += delta;
    this.emit("window", "popstate");
  }
}

class BrowserHarness {
  constructor({ data, ok = true, view = "home", hash = "", dataUrl = "/api/explorer",
    deferredResources = [], failedResources = [] }) {
    this.fetched = [];
    this.scripts = [];
    this.resources = [];
    this.errors = [];
    this.mounted = [];
    this.pending = new Map();
    this.listeners = new Map();
    this.elements = { "load-status": {}, "error-status": {} };
    this.deferredResources = deferredResources;
    this.failedResources = failedResources;
    this.history = new BrowserHistory(
      `https://example.test/docs/explorer/?view=${view}${hash}`,
      (target, type) => this.emit(target, type),
    );
    this.browser = this.createBrowser(data, ok, dataUrl);
    this.initializers = this.createInitializers();
  }

  get body() { return this.browser.document.body; }
  get location() { return this.history.location; }
  get entries() { return this.history.entries; }

  createBrowser(data, ok, dataUrl) {
    const harness = this;
    return {
      document: this.createDocument(),
      get location() { return harness.location; },
      history: this.history,
      UTIMELY_EXPLORER_CONFIG: { dataUrl },
      console: { error: (...args) => this.errors.push(args) },
      addEventListener: (type, callback, options) => this.listen("window", type, callback, options),
      scrollTo() {},
      fetch: async (url, options) => {
        this.fetched.push([url, options.cache]);
        return { ok, status: ok ? 200 : 404, json: async () => data };
      },
    };
  }

  createDocument() {
    const harness = this;
    let html = "";
    return {
      body: {
        className: "",
        classList: { add() {} },
        style: { setProperty() {}, removeProperty() {} },
        get innerHTML() { return html; },
        set innerHTML(value) { html = value; delete harness.elements["error-status"]; },
        prepend(element) { harness.elements[element.id] = element; },
      },
      getElementById: id => this.elements[id],
      querySelector: () => null,
      addEventListener: (type, callback, options) => this.listen("document", type, callback, options),
      createElement: () => ({
        setAttribute() {},
        remove() { delete harness.elements[this.id]; },
      }),
      head: { append: element => this.loadResource(element) },
    };
  }

  createInitializers() {
    const mount = name => signal => {
      const instance = { name, signal, updates: 0 };
      this.mounted.push(instance);
      return { update() { instance.updates++; } };
    };
    return {
      catalog: mount("catalog"), icons: mount("icons"), lineage: mount("lineage"),
      topology: mount("topology"), animation: mount("animation"), highlight() {},
    };
  }

  loadResource(element) {
    const url = element.src || element.href;
    if (element.src) this.scripts.push(url);
    this.resources.push(element);
    if (this.deferredResources.some(part => url.includes(part))) {
      this.pending.set(url, element);
      return;
    }
    queueMicrotask(() => {
      if (this.failedResources.some(part => url.includes(part))) element.onerror();
      else element.onload();
    });
  }

  listen(target, type, callback, { signal } = {}) {
    const key = `${target}:${type}`;
    if (!this.listeners.has(key)) this.listeners.set(key, new Set());
    const callbacks = this.listeners.get(key);
    callbacks.add(callback);
    signal?.addEventListener("abort", () => callbacks.delete(callback), { once: true });
  }

  emit(target, type, event) {
    for (const callback of this.listeners.get(`${target}:${type}`) || []) callback(event);
  }

  settle() {
    return new Promise(resolve => setImmediate(resolve));
  }

  async click(value, options = {}) {
    let prevented = false;
    const link = {
      href: new URL(value, this.location).href,
      target: options.target || "",
      hasAttribute: key => key === "download" && !!options.download,
      getAttribute: () => value,
    };
    this.emit("document", "click", {
      button: 0, ...options, target: { closest: () => link },
      preventDefault() { prevented = true; },
    });
    await this.settle();
    return prevented;
  }

  async back() {
    this.history.move(-1);
    await this.settle();
  }

  async forward() {
    this.history.move(1);
    await this.settle();
  }

  async hash(value) {
    this.history.pushState(null, "", value);
    this.emit("window", "hashchange");
    await this.settle();
  }

  async release(part) {
    for (const [url, element] of this.pending) {
      if (!url.includes(part)) continue;
      element.onload();
      this.pending.delete(url);
    }
    await this.settle();
  }
}

module.exports = { BrowserHarness };
