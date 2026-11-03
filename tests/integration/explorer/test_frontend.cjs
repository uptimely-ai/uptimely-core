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
  const specNavigation = html.match(/aria-label="Spec sections">([^]*?)<\/div>/)[1];
  assert.deepEqual([...specNavigation.matchAll(/<span>([^<]+)<\/span>/g)].map(match => match[1]),
    ["Overview", "Profiles", "Features", "Functions", "Dimensions", "Lineage"]);
  assert.match(specNavigation, /icon--profiles[^>]*data-lucide="layers-2"/);
  assert.match(specNavigation, /icon--dimensions[^>]*data-lucide="axis-3d"/);
  assert.match(specNavigation, /icon--functions[^>]*data-lucide="square-function"/);
  assert.match(html, /icon--invocation-lineage[^>]*data-lucide="git-branch"/);
  assert.match(html, /icon--data-lineage[^>]*data-lucide="monitor-play"/);
  assert.doesNotMatch(html, /icon--home/);
  assert.match(html, /&lt;Test project&gt;/);
  assert.match(html, /Full build/);
  data.scope.is_scoped = true;
  assert.match(shell(data, "home", "", ""), /build-badge-partial/);
});

test("catalogs restore contextual browsing, overview charts and escaped item details", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  for (const view of ["features", "profiles", "dimensions", "functions", "stages"]) {
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
  const profileData = sampleData();
  profileData.catalogs.configuration.profiles.readings.description = "Pump readings per machine.";
  const profiles = renderCatalog(profileData, "profiles").content;
  assert.match(profiles, /data-dataset-schema="readings"/);
  assert.match(profiles, /one row per machine &lt;source&gt;/);
  assert.match(profiles, /<div hidden>\s*<h2>Readings<\/h2>\s*<p data-profile-description>Pump readings per machine\.<\/p>\s*<\/div>\s*<section aria-label="Profile details">/);
  assert.ok(!profiles.includes("2 columns"));
  assert.equal((profiles.match(/Pump readings per machine\./g) || []).length, 1);
  assert.doesNotMatch(profiles, />Profile details</);
  assert.match(profiles, /data-lucide="axis-3d"[^>]*><\/i>Grain<\/h3>/);
  assert.match(profiles, /data-lucide="scan"[^>]*><\/i>Scope<\/h3>/);
  assert.match(profiles, /data-grain-dimension="machine" data-grain-resolution="machine"/);
  assert.match(profiles, /profile-grain-label">Dimension<\/span>\s*<h4>Machine<\/h4>/);
  assert.match(profiles, /class="profile-grain-branch">\s*<section class="profile-grain-resolution" aria-label="Selected resolution">\s*<header><span class="profile-grain-label">Resolution<\/span><h5><code>machine<\/code><\/h5><\/header>\s*<dl class="profile-grain-fields">/);
  assert.match(profiles, /Data key<\/dt><dd><code>id<\/code>/);
  assert.match(profiles, /data-lucide="case-sensitive" class="profile-grain-type-icon" data-type="string"/);
  assert.match(profiles, /data-lucide="hash" class="profile-schema-type-icon" data-type="float"/);
  assert.match(profiles, /<span class="sr-only">float<\/span>/);
  assert.ok(!profiles.includes("one row per machine <source>"));
  assert.ok(!profiles.includes("Filtering"));
  assert.ok(!profiles.includes("Coverage"));
  assert.match(renderCatalog(sampleData(), "stages").content, /Engine type/);
});

test("profile context groups links by category in declaration order", async () => {
  const { catalogContext } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  data.catalogs.configuration.profiles = {
    telemetry: { name: "Telemetry", category: "Measurements <raw>" },
    pumps: { name: "Pumps", category: "Assets" },
    sensors: { name: "Sensors", category: "Measurements <raw>" },
    constants: { name: "Constants" },
    other: { name: "Other", category: "" },
  };
  const html = catalogContext(data, "profiles");
  const groups = [...html.matchAll(/<div class="context-link-group">([^]*?)<\/div>/g)].map(match => match[1]);
  assert.equal(groups.length, 3);
  assert.match(groups[0], /Measurements &lt;raw&gt;.*context-link-count">2/);
  assert.match(groups[0], /href="#profile-telemetry"[^]*href="#profile-sensors"/);
  assert.match(groups[1], /Assets.*context-link-count">1/);
  assert.match(groups[1], /href="#profile-pumps"/);
  assert.match(groups[2], /Uncategorized.*context-link-count">2/);
  assert.match(groups[2], /href="#profile-constants"[^]*href="#profile-other"/);
  assert.match(html, /href="#catalog-overview"/);
  assert.doesNotMatch(html, /Measurements <raw>/);
});

test("profile scope and logical order share a responsive row only when both exist", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  const profile = data.catalogs.configuration.profiles.readings;
  profile.order = [{ dimension: "machine", resolution: "machine", direction: "asc" }];
  const html = renderCatalog(data, "profiles").content;
  assert.match(html, /class="grid gap-6 md:grid-cols-2" data-profile-context/);
  assert.match(html, /Logical order/);
  assert.match(html, /data-lucide="list-ordered"[^>]*><\/i>Logical order<\/h3>/);
  assert.match(html, /Machine · id asc/);
  delete profile.scope;
  assert.doesNotMatch(renderCatalog(data, "profiles").content, /gap-6 md:grid-cols-2" data-profile-context/);
  delete profile.order;
  assert.doesNotMatch(renderCatalog(data, "profiles").content, /data-profile-context/);
});

test("profile actions expose engineering contracts and inspectable bindings", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  const config = data.catalogs.configuration;
  config.functions.aggregate = { name: "Maximum <reading>", kind: "collapse" };
  config.functions.external = { kind: "escape" };
  config.profiles.readings.actions.aggregate = {
    binding: { function: "aggregate", args: { dataset: "$profiles.source.dataframe", options: { method: "<max>" } } },
    features: { inputs: ["$features.raw"], outputs: ["$features.value"] },
  };
  config.profiles.readings.actions.external = {
    binding: { function: "external", args: {} },
    features: { inputs: [], outputs: ["$features.<logical>"] },
  };
  const html = renderCatalog(data, "profiles").content;
  assert.ok(html.indexOf("Produced dataset</h3>") < html.indexOf("Actions</h3>"));
  assert.match(html, /Produced dataset<\/h3><div class="dataset-table-scroll/);
  assert.match(html, /data-lucide="table-2"[^>]*><\/i>Produced dataset<\/h3>/);
  assert.match(html, /data-lucide="square-function"[^>]*><\/i>Actions<\/h3>/);
  assert.match(html, /data-profile-action="aggregate" data-action-kind="collapse"/);
  assert.match(html, /href="\?view=functions#function-aggregate">Maximum &lt;reading&gt;<\/a>/);
  assert.match(html, /Input features<\/dt><dd><code>raw<\/code>/);
  assert.match(html, /Output features<\/dt><dd><code>value<\/code>/);
  assert.match(html, /<details class="profile-action-bindings"><summary>Argument bindings <span>2<\/span>/);
  assert.match(html, /<span class="profile-action-kind">collapse<\/span>\s*<\/header>\s*<details class="profile-action-bindings">/);
  assert.match(html, /<th scope="row">options<\/th><td><code>\{&quot;method&quot;:&quot;&lt;max&gt;&quot;\}/);
  assert.match(html, /Group by grain keys:/);
  assert.match(html, /Output features \(logical\)<\/dt><dd><code>&lt;logical&gt;<\/code>/);
  assert.match(html, /None declared/);
  assert.match(html, /escape outputs are not materialized/);
  assert.ok(!html.includes('data-profile-action="calculate"'));
  assert.ok(!html.includes("<max>"));
});

test("feature catalog excludes dimensions, unused declarations and duplicate outputs", async () => {
  const { features, schemaColumns } = await moduleAt("catalogs/catalog_renderer.js");
  const config = sampleData().catalogs.configuration;
  const profile = config.profiles.readings;
  profile.features.unused = { type: "string" };
  profile.actions.calculate.features.outputs.push("$features.id", "$features.value");
  assert.deepEqual(features(config).map(item => item.featureId), ["value"]);
  assert.deepEqual(schemaColumns(config, profile).map(column => column.role),
    ["Dimension", "Feature", "Feature"]);
});

test("dimension catalog renders resolutions as a parent-linked hierarchy", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  data.catalogs.configuration.dimensions.machine = {
    id: "machine",
    name: "Machine",
    resolutions: {
      machine: { id: "machine", key: "pump_id", type: "string", parent: "production_line" },
      production_line: { id: "production_line", key: "line_id", type: "string", parent: "plant" },
      plant: { id: "plant", key: "plant_id", type: "string" },
    },
  };

  const html = renderCatalog(data, "dimensions").content;
  assert.match(html, /icon--resolutions[^>]*data-lucide="layers-3"/);
  assert.doesNotMatch(html, /icon--resolutions[^>]*data-lucide="braces"/);
  assert.match(html, /aria-label="Resolution hierarchy"/);
  assert.match(html, /dimension-resolution-id">plant<\/h3>/);
  assert.match(html, /<dt><i data-lucide="key-round"[^>]*><\/i>Data key<\/dt>\s*<dd><code>plant_id<\/code>/);
  assert.match(html, /<dt><i data-lucide="braces"[^>]*><\/i>Data type<\/dt>\s*<dd>[^]*?<code>string<\/code>/);
  assert.match(html, /dimension-resolution-level">Top level<\/span>/);
  assert.match(
    html,
    /data-resolution-id="plant"[^]*?<ul class="dimension-resolution-children"[^>]*><li data-resolution-id="production_line"[^]*?<ul class="dimension-resolution-children"[^>]*><li data-resolution-id="machine"/,
  );
  assert.match(html, /dimension-resolution-level">Parent · plant<\/span>/);
  assert.match(html, /data-parent-resolution="production_line"/);
  assert.match(html, /data-parent-resolution="plant"/);
  assert.match(html, /data-lucide="case-sensitive" class="dimension-resolution-type-icon" data-type="string"/);
  assert.match(html, /data-dimension-description[^>]*>No description provided\./);
});

test("dashboard, spec and plan retain original visual components and counts", async () => {
  const { dashboard, specOverview, planOverview } = await moduleAt("rendering/page_renderer.js");
  const data = sampleData();
  const dashboardHtml = dashboard(data);
  assert.match(dashboardHtml, /dashboard-hero/);
  assert.match(dashboardHtml, /<h1><span>&lt;Test project&gt;<\/span><\/h1>/);
  assert.doesNotMatch(dashboardHtml, /<h1 class="title-with-icon">/);
  assert.match(dashboard(data), /dashboard-art/);
  assert.match(dashboard(data), /spec-journey/);
  assert.equal((dashboard(data).match(/data-stat=/g) || []).length, 5);
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
  assert.match(result.content, /data-lucide="hash" class="data-lineage-type-icon" data-type="float"/);
  assert.match(result.content, /1\.23/);
  assert.equal(placeholder({ name: "production_line", role: "Dimension" }, 1, "input"), "pl-2");
  const table = sampleTable([], [{ name: "id", role: "Dimension", type: "string" }],
    "Source input", "input", 3, true, "Readings", ["id"], "removed");
  assert.equal((table.match(/data-join-key/g) || []).length, 4);
  assert.ok(!table.includes("data-dimension-change"));
  assert.match(animation({ animation: { stages: [] } }).content, /No processing steps/);
});
