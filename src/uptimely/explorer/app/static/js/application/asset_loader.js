const ICON_SCRIPT = "https://unpkg.com/lucide@1.67.0/dist/umd/lucide.min.js";
const LINEAGE_SCRIPTS = [
  "https://unpkg.com/force-graph@1.52.0/dist/force-graph.min.js",
  "https://unpkg.com/three@0.160.0/build/three.min.js",
  "https://unpkg.com/3d-force-graph@1.77.0/dist/3d-force-graph.min.js",
  "https://unpkg.com/three-spritetext@1.10.0/dist/three-spritetext.min.js",
];
const HIGHLIGHT_SCRIPT = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js";
const HIGHLIGHT_STYLESHEET = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/monokai-sublime.min.css";

export class AssetLoader {
  constructor(document) {
    this.document = document;
    this.scripts = new Map();
    this.stylesheets = new Map();
  }

  load(url, stylesheet = false) {
    const cache = stylesheet ? this.stylesheets : this.scripts;
    if (cache.has(url)) return cache.get(url).ready;
    const element = this.document.createElement(stylesheet ? "link" : "script");
    if (stylesheet) {
      element.rel = "stylesheet";
      element.href = url;
      element.media = "not all";
    } else {
      element.src = url;
    }
    const ready = new Promise((resolve, reject) => {
      element.onload = resolve;
      element.onerror = () => {
        cache.delete(url);
        element.remove();
        reject(new Error(`Unable to load Explorer ${stylesheet ? "stylesheet" : "library"}: ${url}. Check your network connection and try again.`));
      };
    });
    cache.set(url, { element, ready });
    this.document.head.append(element);
    return ready;
  }

  async loadLineageScripts() {
    for (const url of LINEAGE_SCRIPTS) await this.load(url);
  }

  async prepare(view) {
    const stylesheets = [`./css/${view.stylesheet}.css`];
    const dependencies = [this.load(ICON_SCRIPT)];
    if (view.lineageStyle) dependencies.push(this.loadLineageScripts());
    if (view.highlight) {
      stylesheets.push(HIGHLIGHT_STYLESHEET);
      dependencies.push(this.load(HIGHLIGHT_SCRIPT));
    }
    dependencies.push(...stylesheets.map(url => this.load(url, true)));
    await Promise.all(dependencies);
    return stylesheets;
  }

  activate(urls) {
    for (const [url, { element }] of this.stylesheets) {
      element.media = urls.includes(url) ? "all" : "not all";
    }
  }
}
