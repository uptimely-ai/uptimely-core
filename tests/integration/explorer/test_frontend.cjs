const assert = require("node:assert/strict");
const test = require("node:test");
const { sampleData, moduleAt } = require("./helpers/frontend.cjs");

test("restores the original navigation hierarchy, project identity and build badge", async () => {
  const { shell } = await moduleAt("rendering/shared_markup.js");
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
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
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
  const { features, schemaColumns } = await moduleAt("catalogs/catalog_renderer.js");
  const config = sampleData().catalogs.configuration;
  const dataset = config.entities.asset.datasets.readings;
  dataset.features.unused = { type: "string" };
  dataset.actions.calculate.features.outputs.push("$features.id", "$features.value");
  assert.deepEqual(features(config).map(item => item.featureId), ["value"]);
  assert.deepEqual(schemaColumns(config, config.entities.asset, dataset).map(column => column.role),
    ["Dimension", "Feature", "Feature"]);
});

test("dashboard, spec and plan retain original visual components and counts", async () => {
  const { dashboard, specOverview, planOverview } = await moduleAt("rendering/page_renderer.js");
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
  const { lineage } = await moduleAt("rendering/page_renderer.js");
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
  const { animation, placeholder, sampleTable } = await moduleAt("animation/animation_renderer.js");
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
