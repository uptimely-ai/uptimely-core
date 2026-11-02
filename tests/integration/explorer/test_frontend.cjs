const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");
const test = require("node:test");

const scriptDirectory = path.resolve(__dirname, "../../../src/uptimely/explorer/app/static/js");
const moduleAt = name => import(pathToFileURL(path.join(scriptDirectory, name)).href);

function sampleData() {
  const fn = {
    name: "<Calculate>", description: "Calculate <values>", kind: "vectorize",
    args: { value: { type: "float" } }, return_type: "DataFrame",
    doc: { params: { value: "<Input>" }, examples: ['print("<script>")'], raises: [] },
    entrypoint: "example:calculate",
  };
  const column = { name: "value", label: "<Value>", role: "Output", type: "float" };
  return {
    format_version: 1,
    project: { name: "<Test project>", spec_version: 3 },
    scope: { label: "all features", is_scoped: false },
    catalogs: {
      configuration: {
        entities: { asset: { name: "<Asset>", dimensions: ["id"], datasets: {
          readings: {
            name: "Readings", features: { value: { name: "<Value>", type: "float" } },
            actions: { calculate: { binding: { function: "calculate", args: {} }, features: { inputs: [], outputs: ["$features.value"] } } },
            row_scope: { grain: "one row" },
          },
        } } },
        dimensions: { id: { name: "Asset ID", type: "string" } },
        functions: { calculate: fn },
      },
      summary: { entity_count: 1, dataset_count: 1, action_count: 1, dimension_count: 1,
        feature_count: 1, function_count: 1, feature_buckets: { input: 0, output: 1 },
        function_buckets: { vectorize: 1 } },
      function_groups: { vectorize: { calculate: fn } },
    },
    graphs: {
      feature_lineage: { nodes: [{ id: "value", label: "</script><script>alert(1)</script>" }], links: [] },
      invocation_lineage: { nodes: [], links: [] },
      feature_style: { function_color: "#ffffff", background_color: "#101820" },
      invocation_style: { background_color: "#101820" },
    },
    plan: { stage_count: 1, invocation_count: 1, function_count: 1, entity_count: 1,
      feature_count: 1, dependency_count: 0, max_parallel_invocations: 1,
      function_kind_counts: [["vectorize", 1]] },
    stages: [{ stage: 1, steps: [{
      title: "<Calculate>", function: "calculate", function_label: "Calculate",
      function_kind: "vectorize", entity: "asset", dataset: "readings",
      input_features: [], output_features: ["value"], depends_on_invocations: [],
      args: { value: { value: "<input>", type: { engine: "float" } } },
      returns: { type: { engine: "DataFrame" } }, row_context: null,
    }] }],
    animation: { stages: [[{
      number: 1, invocation_id: "calculate:readings", function_label: "Calculate",
      function: "calculate", entity: "asset", dataset: "readings", dataset_label: "Readings",
      action: "<Calculate>", dependencies: [], columns: [column], main_columns: [column],
      kind: { id: "vectorize" }, input_tables: [], row_count: 3,
    }]] },
  };
}

test("restores the original navigation hierarchy, project identity and build badge", async () => {
  const { shell } = await moduleAt("ui.js");
  const data = sampleData();
  const html = shell(data, "functions", "", "");
  for (const section of ["Spec sections", "Plan sections", "Execution sections"]) assert.ok(html.includes(section));
  assert.match(html, /id="explorer-navigation"/);
  assert.match(html, /nav-label-toggle/);
  assert.match(html, /href="\?view=functions" aria-current="page"/);
  assert.match(html, /&lt;Test project&gt;/);
  assert.match(html, /Full build/);
  data.scope.is_scoped = true;
  assert.match(shell(data, "home", "", ""), /build-badge-partial/);
});

test("catalogs restore contextual browsing, overview charts and escaped item details", async () => {
  const { renderCatalog } = await moduleAt("catalogs.js");
  for (const view of ["features", "entities", "datasets", "dimensions", "functions", "stages"]) {
    const { content, context } = renderCatalog(sampleData(), view);
    assert.match(context, /id="catalog-context"/);
    assert.match(context, /href="#catalog-overview"/);
    assert.match(content, /id="catalog-overview" data-context-item/);
    assert.match(content, /data-category=/);
    assert.ok(!content.includes("<Calculate>"));
    assert.ok(!content.includes("<input>"));
  }
  const functions = renderCatalog(sampleData(), "functions");
  assert.match(functions.content, /data-function-group="vectorize"/);
  assert.match(functions.content, /language-python/);
  assert.match(functions.content, /&lt;script&gt;/);
  assert.match(functions.content, /DataFrame/);
  assert.match(functions.context, /href="#function-calculate"/);
  assert.match(renderCatalog(sampleData(), "datasets").content, /data-dataset-schema="readings"/);
  assert.match(renderCatalog(sampleData(), "stages").content, /Engine type/);
});

test("feature catalog excludes dimensions, unused declarations and duplicate outputs", async () => {
  const { features, schemaColumns } = await moduleAt("catalogs.js");
  const config = sampleData().catalogs.configuration;
  const dataset = config.entities.asset.datasets.readings;
  dataset.features.unused = { type: "string" };
  dataset.actions.calculate.features.outputs.push("$features.id", "$features.value");
  assert.deepEqual(features(config).map(item => item.featureId), ["value"]);
  assert.deepEqual(schemaColumns(config, config.entities.asset, dataset).map(column => column.role),
    ["Dimension", "Feature", "Feature"]);
});

test("dashboard, spec and plan retain original visual components and counts", async () => {
  const { dashboard, specOverview, planOverview } = await moduleAt("views.js");
  const data = sampleData();
  assert.match(dashboard(data), /dashboard-hero/);
  assert.match(dashboard(data), /dashboard-art/);
  assert.match(dashboard(data), /spec-journey/);
  assert.equal((dashboard(data).match(/data-stat=/g) || []).length, 6);
  assert.match(specOverview(data), /Spec profile/);
  assert.match(specOverview(data), /data-generated="false"/);
  assert.match(planOverview(data), /Max parallel invocations/);
});

test("lineage views expose original canvases, controls and script-safe graph data", async () => {
  const { lineage } = await moduleAt("views.js");
  const feature = lineage(sampleData(), false);
  assert.match(feature.content, /id="lineage-2d"/);
  assert.match(feature.content, /id="lineage-3d"/);
  assert.match(feature.context, /data-dimension="3d"/);
  assert.match(feature.context, /id="node-details"/);
  assert.ok(!feature.content.includes("</script><script>"));
  const payload = feature.content.match(/id="graph-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  assert.deepEqual(JSON.parse(payload), sampleData().graphs.feature_lineage);
  assert.match(lineage(sampleData(), true).context, /id="invocation-node-details"/);
});

test("animation restores dataset selection, table schemas and playback component contracts", async () => {
  const { animation, placeholder, sampleTable } = await moduleAt("animation.js");
  const result = animation(sampleData());
  for (const id of ["animation-dataset", "data-lineage-play", "data-lineage-next", "data-lineage-previous"]) {
    assert.ok(result.context.includes(`id="${id}"`));
  }
  assert.match(result.context, /data-animation-dataset="1"/);
  assert.match(result.context, /data-animation-step="1"/);
  assert.match(result.content, /id="step-1"/);
  assert.match(result.content, /data-invocation-id="calculate:readings"/);
  assert.match(result.content, /data-role="Output" data-column="value"/);
  assert.match(result.content, /data-side="output"/);
  assert.match(result.content, /1\.23/);
  assert.equal(placeholder({ name: "production_line", role: "Dimension" }, 1, "input"), "pl-2");
  const table = sampleTable([], [{ name: "id", role: "Dimension", type: "string" }],
    "Source input", "input", 3, true, "Readings", ["id"], "removed");
  assert.equal((table.match(/data-join-key/g) || []).length, 4);
  assert.ok(!table.includes("data-dimension-change"));
  assert.match(animation({ animation: { stages: [] } }).content, /No processing steps/);
});

async function boot({ ok = true, data = sampleData(), view = "home", dataUrl = "/api/explorer", hash = "" } = {}) {
  const { shell } = await moduleAt("ui.js");
  const views = await moduleAt("views.js");
  const elements = { "load-status": {}, "error-status": {} };
  const body = { className: "", classList: { add() {} }, style: { setProperty() {} } };
  const fetched = [], scripts = [], errors = [], redirects = [];
  const context = vm.createContext({
    ...views, shell, URL, URLSearchParams, console: { error: (...args) => errors.push(args) },
    window: { UTIMELY_EXPLORER_CONFIG: { dataUrl }, addEventListener() {} },
    location: { search: `?view=${view}`, href: `https://example.test/docs/explorer/?view=${view}${hash}`, hash,
      replace: url => redirects.push(url) },
    document: {
      body, getElementById: id => elements[id],
      createElement: () => ({}), head: { append(script) { if (script.src) scripts.push(script.src); script.onload(); } },
    },
    fetch: async (url, options) => {
      fetched.push([url, options.cache]);
      return { ok, status: ok ? 200 : 404, json: async () => data };
    },
  });
  let source = fs.readFileSync(path.join(scriptDirectory, "app.js"), "utf8");
  source = source.replace(/^import .*;\n/gm, "")
    .replace(/await import\("[^"]+"\)/g, "Promise.resolve()");
  await vm.runInContext(`(async () => { ${source} })()`, context);
  return { body, elements, fetched, scripts, errors, redirects };
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

test("preserves migrated hash bookmarks and reports missing, incompatible or unknown data explicitly", async () => {
  const legacy = await boot({ hash: "#feature-lineage" });
  assert.equal(legacy.redirects[0], "https://example.test/docs/explorer/?view=lineage");
  const missing = await boot({ ok: false });
  assert.match(missing.elements["error-status"].textContent, /HTTP 404/);
  assert.match(missing.elements["error-status"].textContent, /uptimely project build/);
  const incompatible = await boot({ data: { format_version: 999 } });
  assert.match(incompatible.elements["error-status"].textContent, /unsupported format/);
  const unknown = await boot({ view: "<unknown>" });
  assert.match(unknown.elements["error-status"].textContent, /Unknown Explorer page/);
  assert.equal(unknown.fetched.length, 0);
});
