const assert = require("node:assert/strict");
const test = require("node:test");
const { sampleData, moduleAt } = require("./helpers/frontend.cjs");
const { BrowserHarness } = require("./helpers/browser.cjs");

async function boot(options = {}) {
  const { Explorer } = await moduleAt("application/explorer_application.js");
  const harness = new BrowserHarness({ data: sampleData(), ...options });
  harness.explorer = new Explorer(harness.browser, harness.initializers);
  await harness.explorer.start();
  return harness;
}

test("boots from configurable live or nested-export data URLs without changing the snapshot contract", async () => {
  for (const dataUrl of ["/api/explorer", "./data/explorer.json"]) {
    const result = await boot({ dataUrl });
    assert.deepEqual(result.fetched, [[dataUrl, "no-store"]]);
    assert.match(result.body.innerHTML, /dashboard-hero/);
    assert.equal(result.errors.length, 0);
    assert.ok(result.scripts.some(url => url.includes("lucide@")));
  }
});

test("nested static exports navigate run pages without contacting live APIs", async () => {
  const { Explorer } = await moduleAt("application/explorer_application.js");
  const data = sampleData();
  const app = new BrowserHarness({ data, dataUrl: "./data/explorer.json" });
  const snapshot = {
    run: {
      run_id: "static-demo", status: "succeeded", duration_seconds: 0.1,
      build: { fingerprint: "demo", manifest: { features: null } },
      profiles: { readings: {} },
    },
    logs: [{ level: "debug", logger: "demo", message: "Saved debug event", timestamp: "" }],
    previews: {
      readings: {
        status: "succeeded", columns: [{ name: "value", dtype: "Int64" }], rows: [[42]],
      },
    },
  };
  app.browser.UTIMELY_EXPLORER_CONFIG.runDataUrl = "./data/run.json";
  app.browser.document.querySelectorAll = () => [];
  app.browser.fetch = async (url, options) => {
    assert.ok(["./data/explorer.json", "./data/run.json"].includes(url), url);
    app.fetched.push([url, options.cache]);
    return { ok: true, json: async () => url === "./data/run.json" ? snapshot : data };
  };
  app.explorer = new Explorer(app.browser, app.initializers);
  await app.explorer.start();

  for (const [view, expected] of [
    ["info", /static-demo/], ["logs", /Saved debug event/], ["preview", />42<\/td>/],
  ]) {
    assert.equal(await app.click(`?view=${view}`), true);
    assert.equal(app.explorer.views.activeView, view);
    assert.match(app.body.innerHTML, expected);
  }
  assert.deepEqual(app.fetched, [
    ["./data/explorer.json", "no-store"], ...Array(3).fill(["./data/run.json", "no-store"]),
  ]);
  assert.deepEqual(app.errors, []);
});

test("preserves migrated hash bookmarks and reports missing, incompatible or unknown data explicitly", async () => {
  const legacy = await boot({ hash: "#feature-lineage" });
  assert.equal(legacy.location.href, "https://example.test/docs/explorer/?view=lineage");
  const missing = await boot({ ok: false });
  assert.match(missing.elements["error-status"].textContent, /HTTP 404/);
  assert.match(missing.elements["error-status"].textContent, /uptimely project build/);
  const incompatible = await boot({ data: { format_version: 999 } });
  assert.match(incompatible.elements["error-status"].textContent, /unsupported format/);
  const unknown = await boot({ view: "<unknown>" });
  assert.match(unknown.elements["error-status"].textContent, /Unknown Explorer page/);
  assert.equal(unknown.fetched.length, 0);
});

test("internal navigation reuses the document, snapshot and libraries while remounting views", async () => {
  const app = await boot();
  for (const view of ["features", "functions", "animation", "lineage", "topology", "home", "functions", "animation"]) {
    assert.equal(await app.click(`?view=${view}`), true);
    assert.equal(new URL(app.location.href).searchParams.get("view"), view);
    assert.match(app.body.innerHTML, new RegExp(`href="\\?view=${view}"`));
  }
  assert.equal(app.fetched.length, 1);
  assert.equal(new Set(app.scripts).size, app.scripts.length);
  for (const instance of app.mounted.slice(0, -2)) assert.equal(instance.signal.aborted, true, instance.name);
  assert.equal(app.mounted.at(-1).name, "animation");
  assert.equal(app.mounted.at(-1).signal.aborted, false);
  const enabled = app.resources.filter(element => element.href && element.media === "all");
  assert.equal(enabled.length, 1);
  assert.equal(enabled[0].href, "./css/data_lineage.css");
  assert.deepEqual(app.errors, []);
});

test("browser back/forward and item hashes update the active view without stale components", async () => {
  const app = await boot();
  await app.click("?view=features#feature-readings-value");
  const catalog = app.mounted.find(instance => instance.name === "catalog");
  await app.hash("#catalog-overview");
  assert.equal(catalog.updates, 1);
  await app.click("?view=animation#step-1");
  assert.equal(catalog.signal.aborted, true);
  await app.back();
  assert.match(app.location.href, /view=features#catalog-overview$/);
  assert.equal(app.mounted.at(-2).name, "catalog");
  await app.back();
  assert.match(app.location.href, /#feature-readings-value$/);
  assert.equal(app.mounted.at(-2).updates, 1);
  await app.forward();
  await app.forward();
  assert.equal(app.mounted.at(-1).name, "animation");
  assert.equal(app.fetched.length, 1);
  assert.deepEqual(app.errors, []);
});

test("same-page lineage options update the graph component without refetching or remounting", async () => {
  const app = await boot({ view: "lineage" });
  const lineage = app.mounted.find(instance => instance.name === "lineage");
  const mounts = app.mounted.length;
  await app.click("?view=lineage&operators=hide");
  assert.equal(lineage.updates, 1);
  await app.back();
  assert.equal(lineage.updates, 2);
  await app.forward();
  assert.equal(lineage.updates, 3);
  assert.equal(app.mounted.length, mounts);
  assert.equal(app.fetched.length, 1);
  assert.deepEqual(app.errors, []);
  app.explorer.dispose();
});

test("modified, external, download and local fragment clicks keep native browser behavior", async () => {
  const app = await boot();
  for (const options of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true },
    { button: 1 }, { target: "_blank" }, { download: true }, { defaultPrevented: true }]) {
    assert.equal(await app.click("?view=features", options), false);
  }
  assert.equal(await app.click("https://external.test/?view=features"), false);
  assert.equal(await app.click("/different/path/?view=features"), false);
  assert.equal(await app.click("#catalog-overview"), false);
  assert.equal(app.entries.length, 1);
});

test("a slow route cannot overwrite a newer route or enable its stylesheet", async () => {
  const app = await boot({ deferredResources: ["force-graph@"] });
  await app.click("?view=lineage");
  assert.match(app.body.innerHTML, /dashboard-hero/);
  await app.click("?view=functions");
  const latest = app.body.innerHTML;
  await app.release("force-graph@");
  await app.release("force-graph@");
  assert.equal(app.body.innerHTML, latest);
  assert.equal(app.mounted.at(-1).name, "icons");
  assert.equal(app.resources.find(element => element.href === "./css/lineage.css").media, "not all");
});

test("failed dependencies report an error and allow returning to the active page", async () => {
  const failedResources = ["highlight.min.js"];
  const app = await boot({ failedResources });
  await app.click("?view=functions");
  assert.equal(app.elements["error-status"].hidden, false);
  assert.match(app.elements["error-status"].textContent, /Unable to load Explorer library/);
  assert.match(app.body.innerHTML, /dashboard-hero/);
  await app.click("?view=home");
  assert.equal(app.elements["error-status"], undefined);
  failedResources.length = 0;
  await app.click("?view=functions");
  assert.equal(app.elements["error-status"], undefined);
  assert.match(app.body.innerHTML, /Functions overview/);
  assert.equal(app.scripts.filter(url => url.includes("highlight.min.js")).length, 2);
  assert.equal(app.fetched.length, 1);
});

test("disposing the application cancels pending routes and removes navigation listeners", async () => {
  const app = await boot({ deferredResources: ["force-graph@"] });
  await app.click("?view=lineage");
  app.explorer.dispose();
  await app.release("force-graph@");
  await app.release("force-graph@");
  assert.match(app.body.innerHTML, /dashboard-hero/);
  assert.ok(app.mounted.every(instance => instance.signal.aborted));
  assert.equal(await app.click("?view=features"), false);
  assert.equal(app.entries.length, 2);
  assert.deepEqual(app.errors, []);
});

test("a component initialization failure aborts its resources and allows another view", async () => {
  const app = await boot();
  let failedSignal;
  app.initializers.animation = signal => {
    failedSignal = signal;
    throw new Error("Playback setup failed");
  };
  await app.click("?view=animation");
  assert.equal(failedSignal.aborted, true);
  assert.match(app.elements["error-status"].textContent, /Playback setup failed/);
  await app.click("?view=home");
  assert.match(app.body.innerHTML, /dashboard-hero/);
  assert.equal(app.elements["error-status"], undefined);
});

test("disposing during startup does not mount a view or attach navigation listeners", async () => {
  const { Explorer } = await moduleAt("application/explorer_application.js");
  const app = new BrowserHarness({ data: sampleData() });
  const fetchData = app.browser.fetch;
  let release;
  app.browser.fetch = (...args) => new Promise(resolve => {
    release = () => resolve(fetchData(...args));
  });
  const explorer = new Explorer(app.browser, app.initializers);
  const startup = explorer.start();
  explorer.dispose();
  release();
  await startup;
  assert.deepEqual(app.mounted, []);
  assert.equal(await app.click("?view=features"), false);
  assert.deepEqual(app.errors, []);
});

test("only declared legacy hashes and view names are accepted as routes", async () => {
  for (const hash of ["#toString", "#constructor", "#__proto__"]) {
    const app = await boot({ hash });
    assert.equal(app.location.hash, hash);
    assert.match(app.body.innerHTML, /dashboard-hero/);
    assert.deepEqual(app.errors, []);
  }
  const unknown = await boot({ view: "toString" });
  assert.match(unknown.elements["error-status"].textContent, /Unknown Explorer page/);
});
