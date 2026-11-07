const assert = require("node:assert/strict");
const test = require("node:test");
const { sampleData, moduleAt } = require("./helpers/frontend.cjs");

test("navigation shows model, plan and run results with project identity and build badge", async () => {
  const { shell } = await moduleAt("rendering/shared_markup.js");
  const data = sampleData();
  const html = shell(data, "functions", "", "");
  for (const section of ["Analytical model sections", "Execution plan sections", "Run results sections"]) assert.ok(html.includes(section));
  assert.match(html, /id="explorer-navigation"/);
  assert.match(html, /nav-label-toggle/);
  assert.match(html, /href="\?view=functions" aria-current="page"/);
  const specNavigation = html.match(/aria-label="Analytical model sections">([^]*?)<\/div>/)[1];
  assert.deepEqual([...specNavigation.matchAll(/<span>([^<]+)<\/span>/g)].map(match => match[1]),
    ["Profiles", "Features", "Functions", "Dimensions", "Lineage"]);
  assert.match(specNavigation, /icon--profiles[^>]*data-lucide="layers-2"/);
  assert.match(specNavigation, /icon--dimensions[^>]*data-lucide="axis-3d"/);
  assert.match(specNavigation, /icon--functions[^>]*data-lucide="square-function"/);
  assert.match(html, /icon--invocation-lineage[^>]*data-lucide="layout-arrow-right"/);
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
    if (view === "profiles") {
      assert.match(content, /class="profile-summary-category"/);
    } else {
      assert.match(content, /data-category=/);
    }
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
  const secondProfile = structuredClone(profileData.catalogs.configuration.profiles.readings);
  secondProfile.name = "Daily readings";
  secondProfile.category = "Batch";
  secondProfile.assembly = Object.fromEntries(
    ["load", "aggregate", "write"].map(id => [id, structuredClone(secondProfile.assembly.calculate)]),
  );
  profileData.catalogs.configuration.profiles.daily = secondProfile;
  profileData.catalogs.summary.operator_count = 400;
  const profileCatalog = renderCatalog(profileData, "profiles");
  const profiles = profileCatalog.content;
  assert.match(profileCatalog.context, /href="#catalog-overview"[^]*?>Overview/);
  assert.equal((profiles.match(/class="profile-summary-card"/g) || []).length, 2);
  assert.match(profiles, /href="#profile-readings"[^]*?class="profile-summary-meter"[^]*?class="profile-summary-size"><strong>1<\/strong><span>operator<\/span>/);
  assert.match(profiles, /href="#profile-daily"[^]*?class="profile-summary-meter"[^]*?class="profile-summary-size"><strong>3<\/strong><span>operators<\/span>/);
  const profileOverview = profiles.slice(0, profiles.indexOf('<div class="space-y-8">'));
  assert.match(profileOverview, /profile-summary-grain-path" aria-label="Machine dimension at machine resolution"[^]*?<span class="profile-summary-grain-badge profile-summary-grain-resolution">[^]*?icon--resolutions profile-summary-grain-icon" data-lucide="scan-square"[^]*?<code>machine<\/code><\/span>\s*<i class="profile-summary-grain-relation" data-lucide="at-sign"[^]*><\/i>\s*<span class="profile-summary-grain-badge profile-summary-grain-dimension">[^]*?icon--dimensions profile-summary-grain-icon" data-lucide="axis-3d"[^]*?<strong>Machine<\/strong><\/span>/);
  assert.match(profileOverview, /profile-summary-grain-icon/);
  assert.doesNotMatch(profileOverview, /<span>Dimension<\/span>|<span>Resolution<\/span>/);
  assert.doesNotMatch(profileOverview, /<code>readings<\/code>|<code>daily<\/code>|\b2 features\b/);
  assert.doesNotMatch(profiles, /Profiles stats|Profiles by category/);
  assert.match(profiles, /data-dataset-schema="readings"/);
  assert.match(profiles, /one row per machine &lt;source&gt;/);
  assert.match(profiles, /<div hidden>\s*<h2>Readings<\/h2>\s*<p data-profile-description>Pump readings per machine\.<\/p>\s*<\/div>\s*<section aria-label="Profile details">/);
  assert.ok(!profiles.includes("2 columns"));
  assert.equal((profiles.match(/Pump readings per machine\./g) || []).length, 2);
  assert.doesNotMatch(profiles, />Profile details</);
  assert.match(profiles, /profile-detail-subheading[^>]*>[^]*?<span>Grain<\/span><\/h3>/);
  assert.match(profiles, /profile-detail-subheading[^>]*>[^]*?<span>Scope<\/span><\/h3>/);
  assert.match(profiles, /profile-summary-grain-path" aria-label="Machine dimension at machine resolution"[^]*?<code>machine<\/code>[^]*?<strong>Machine<\/strong>/);
  assert.doesNotMatch(profiles, /data-grain-dimension|profile-grain-label|profile-grain-fields/);
  assert.match(profiles, /data-type="string"/);
  assert.match(profiles, /data-lucide="hash" class="data-type-label-icon" data-type="float"/);
  assert.match(profiles, /aria-label="value \(float\)"/);
  assert.doesNotMatch(profiles, /<th[^>]*>Data type<\/th>/);
  assert.ok(!profiles.includes("one row per machine <source>"));
  assert.ok(!profiles.includes("Filtering"));
  assert.ok(!profiles.includes("Coverage"));
  const stages = renderCatalog(sampleData(), "stages").content;
  assert.match(stages, /aria-label="value \(float\)"/);
  assert.doesNotMatch(stages, /Binding type|Function type|Engine type|<th[^>]*>Data type<\/th>/);
});

test("merge phases expose their invocation metadata and owning operator", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const { lineage } = await moduleAt("rendering/page_renderer.js");
  const data = sampleData();
  const merge = {
    invocation_id: "invocation:merge:join:readings:calculate",
    operator_id: "calculate",
    phase: "merge",
    function: "join",
    function_kind: "merge",
    title: "Join results",
    function_label: "Join results",
    merge_target: "readings",
    fragment_source: "$operators.calculate.fragment",
    merge_keys: ["id"],
    profile: "readings",
    dataset: "readings",
    dataset_label: "Readings",
    input_features: [],
    output_features: [],
    input_feature_ids: [],
    output_feature_ids: [],
    uncontrolled: false,
    row_context: null,
    depends_on_invocations: [{ id: "read", function: "Read values", phase: "compute" }],
    args: {
      target: { value: "readings", type: { function: "dataframe | null" } },
      fragment: { value: "$operators.calculate.fragment", type: { function: "dataframe" } },
      target_keys: { value: ["id"], type: { function: "array[string]" } },
    },
    returns: { type: { engine: "DataFrame" } },
  };
  data.stages = [{ stage: 1, steps: [merge] }];
  data.graphs.invocation_lineage = {
    nodes: [{
      id: merge.invocation_id,
      phase: "merge",
      function_kind: "merge",
      function_name: merge.function_label,
      operator_id: merge.operator_id,
      dataset_id: "readings",
      merge_target: merge.merge_target,
      fragment_source: merge.fragment_source,
      merge_keys: merge.merge_keys,
      arguments: { target: "readings" },
      dependency_ids: ["read"],
      stage: 1,
    }],
    links: [{ source: "read", target: merge.invocation_id, dependency_type: "fragment" }],
  };
  data.catalogs.configuration.profiles.readings.assembly.calculate.merge = {
    function: "join",
    args: { target: "$profiles.@.dataframe", fragment: "$operators.@.fragment", target_keys: ["id"] },
  };
  data.catalogs.configuration.functions.join = { name: "Join results", kind: "merge" };
  data.catalogs.function_groups.merge = { join: data.catalogs.configuration.functions.join };

  const stages = renderCatalog(data, "stages").content;
  const profiles = renderCatalog(data, "profiles").content;
  const topology = lineage(data, true).content;
  assert.match(stages, /data-phase="merge"/);
  assert.match(stages, /Merge target/);
  assert.match(stages, /Fragment source/);
  assert.match(stages, /Merge keys/);
  assert.match(profiles, /id="operator-readings-calculate"/);
  assert.match(profiles, /profile-operator-merge-indicator/);
  assert.match(profiles, /data-lucide="git-merge"/);
  assert.match(profiles, /The resulting fragment produced from a foreign profile needs to be merged into this profile's dataset\./);
  assert.match(topology, /"phase":"merge"/);
  assert.match(topology, /"dependency_type":"fragment"/);
});

test("mobile navigation separates the main menu from page controls", async () => {
  const { shell } = await moduleAt("rendering/shared_markup.js");
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const { lineage } = await moduleAt("rendering/page_renderer.js");
  const { animation } = await moduleAt("animation/animation_renderer.js");
  const data = sampleData();
  const pages = [
    ...["features", "profiles", "dimensions", "functions", "stages"].map(view => renderCatalog(data, view)),
    lineage(data, false), lineage(data, true), animation(data),
    { context: "", content: "" },
  ];
  for (const { context, content } of pages) {
    const html = shell(data, "functions", context, content);
    assert.match(html, /class="mobile-nav-toggle"[^>]*aria-controls="explorer-navigation"/);
    const menus = html.slice(html.indexOf('<div class="site-menus"'), html.indexOf('<div class="site-content"'));
    assert.match(menus, /id="explorer-menus"/);
    assert.match(menus, /id="explorer-navigation"/);
    assert.ok(menus.includes(context));
    if (context) {
      assert.match(html, /class="mobile-context-bar"/);
      assert.match(html, /class="mobile-context-toggle ui-button"/);
      assert.doesNotMatch(html, /mobile-context-selection/);
      assert.match(html, /data-lucide="chevron-down"/);
      assert.doesNotMatch(html, /data-lucide="chevron-up"/);
      assert.match(context, /class="ui-button context-sheet-close"/);
    } else {
      assert.doesNotMatch(html, /mobile-context-bar/);
    }
    assert.doesNotMatch(html, /class="ui-button context-back"|catalog-context-toggle|>Browse \w+<\/button>/);
  }
  for (const view of ["lineage", "topology"]) {
    const markup = lineage(data, view === "topology");
    const html = shell(data, view, markup.context, markup.content);
    assert.match(html, /<span>Legend &amp; details<\/span>/);
    assert.doesNotMatch(html, /<span>Graph controls<\/span>/);
  }
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
  assert.match(html, /profile-detail-subheading[^>]*>[^]*?<span>Logical order<\/span><\/h3>/);
  assert.match(html, /Machine · id asc/);
  delete profile.scope;
  assert.doesNotMatch(renderCatalog(data, "profiles").content, /gap-6 md:grid-cols-2" data-profile-context/);
  delete profile.order;
  assert.doesNotMatch(renderCatalog(data, "profiles").content, /data-profile-context/);
});

test("profile operator expose engineering contracts and inspectable bindings", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  const config = data.catalogs.configuration;
  config.functions.aggregate = { name: "Maximum <reading>", kind: "collapse" };
  config.functions.external = { kind: "escape" };
  config.profiles.readings.assembly.aggregate = {
    compute: { function: "aggregate", args: { dataset: "$profiles.source.dataframe", options: { method: "<max>" } } },
    interface: { inputs: ["$features.raw"], outputs: ["$features.value"] },
  };
  config.profiles.readings.assembly.external = {
    compute: { function: "external", args: {} },
    interface: { inputs: [], outputs: ["$features.<logical>"] },
  };
  data.stages[0].steps.push({
    profile: "readings",
    operator_id: "aggregate",
    phase: "compute",
    args: {
      dataset: { value: "$profiles.source.dataframe", type: { engine: "DataFrame" } },
      options: { value: { method: "<max>" }, type: { function: "dict" } },
    },
  });
  const html = renderCatalog(data, "profiles").content;
  assert.ok(html.indexOf("<span>Produced schema</span></h3>") < html.indexOf("<span>Assembly</span></h3>"));
  assert.match(html, /<span>Produced schema<\/span><\/h3><div class="ui-table-scroll profile-schema-scroll/);
  assert.match(html, /profile-detail-subheading[^>]*>[^]*?<span>Assembly<\/span><\/h3>/);
  assert.match(html, /profile-operator-kicker">OPERATION<\/span>/);
  assert.match(html, /<div class="profile-operator-list">/);
  assert.doesNotMatch(html, /<div class="profile-operator">/);
  assert.match(html, /data-profile-operator="aggregate" data-operator-kind="collapse"/);
  assert.match(html, /href="\?view=functions#function-aggregate">Maximum &lt;reading&gt;<\/a>/);
  assert.match(html, /Input features<\/dt><dd><code>raw<\/code>/);
  assert.match(html, /Output features<\/dt><dd><code>value<\/code>/);
  assert.match(html, /<details class="profile-operator-bindings profile-operator-bindings-inline"><summary>Resolved arguments<\/summary>/);
  assert.match(html, /<code class="language-json">\{&quot;method&quot;:&quot;&lt;max&gt;&quot;\}<\/code>/);
  assert.match(html, /This value will be bound only during the engine execution\./);
  assert.doesNotMatch(html, /Group by grain keys:|ui-badge--neutral">collapse/);
  assert.match(html, /Output features \(logical\)<\/dt><dd><code>&lt;logical&gt;<\/code>/);
  assert.match(html, /None declared/);
  assert.match(html, /escape outputs are not materialized/);
  assert.match(html, /data-profile-operator="calculate" data-operator-kind="vectorize"/);
  assert.match(html, /data-lucide="table-properties"/);
  assert.ok(!html.includes("<max>"));
});

test("feature catalog excludes dimensions, unused declarations and duplicate outputs", async () => {
  const { features, schemaColumns } = await moduleAt("catalogs/catalog_renderer.js");
  const config = sampleData().catalogs.configuration;
  const profile = config.profiles.readings;
  profile.features.unused = { type: "string" };
  profile.assembly.calculate.interface.outputs.push("$features.id", "$features.value");
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
  assert.match(html, /aria-label="Resolution levels"/);
  assert.match(html, /dimension-resolution-id"><span class="typed-name" title="string" aria-label="plant \(string\)">[^]*?<span>plant<\/span><\/span><\/h3>/);
  const hierarchy = html.match(/<ul aria-label="Resolution hierarchy"[^]*?<\/section>/)[0];
  assert.doesNotMatch(hierarchy, /<code>plant_id<\/code>|>string<\/span>/);
  assert.doesNotMatch(html, /dimension-resolution-level|dimension-resolution-fields/);
  assert.match(
    html,
    /data-resolution-id="plant"[^]*?<ul class="dimension-resolution-children"[^>]*><li data-resolution-id="production_line"[^]*?<ul class="dimension-resolution-children"[^>]*><li data-resolution-id="machine"/,
  );
  assert.match(html, /data-parent-resolution="production_line"/);
  assert.match(html, /data-parent-resolution="plant"/);
  assert.match(html, /data-lucide="case-sensitive" class="data-type-label-icon" data-type="string"/);
  assert.match(html, /data-dimension-description[^>]*>No description provided\./);
});

test("dashboard, Features charts and plan show visual components and counts", async () => {
  const { dashboard, planOverview } = await moduleAt("rendering/page_renderer.js");
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  const dashboardHtml = dashboard(data);
  assert.match(dashboardHtml, /dashboard-hero/);
  assert.match(dashboardHtml, /<h1><span>&lt;Test project&gt;<\/span><\/h1>/);
  assert.doesNotMatch(dashboardHtml, /<h1 class="title-with-icon">/);
  assert.match(dashboard(data), /dashboard-art/);
  assert.match(dashboard(data), /spec-journey/);
  assert.equal((dashboard(data).match(/data-stat=/g) || []).length, 5);
  const features = renderCatalog(data, "features").content;
  assert.match(features, /Features by role/);
  assert.match(features, /Features by data type/);
  assert.match(features, /data-section-count class="ui-badge">1 features<\/span>/);
  assert.doesNotMatch(features, /<h2[^>]*>Features overview<\/h2>|data-stat=/);
  assert.match(features, /data-category="output" data-count="1"/);
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
  assert.match(result.content, /data-lucide="hash" class="data-type-label-icon" data-type="float"/);
  assert.match(result.content, /1\.23/);
  assert.equal(placeholder({ name: "production_line", role: "Dimension" }, 1, "input"), "pl-2");
  const table = sampleTable([], [{ name: "id", role: "Dimension", type: "string" }],
    "Source input", "input", 3, true, "Readings", ["id"], "removed");
  assert.equal((table.match(/data-join-key/g) || []).length, 4);
  assert.ok(!table.includes("data-dimension-change"));
  assert.match(animation({ animation: { stages: [] } }).content, /No processing steps/);
});
