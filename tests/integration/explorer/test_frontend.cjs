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
    assert.match(context, /href="#overview"/);
    assert.match(content, /id="overview" data-context-item/);
    if (view === "profiles") {
      assert.match(content, /class="profile-summary-category"/);
    } else {
      assert.match(content, /data-category=/);
    }
    assert.ok(!content.includes("<Calculate>"));
    assert.ok(!content.includes("<input>"));
  }
  const functions = renderCatalog(sampleData(), "functions");
  assert.match(functions.content, /data-function-group="Uncategorized"/);
  assert.match(functions.content, /language-python/);
  assert.match(functions.content, /<span class="ui-badge[^>]*>Python<\/span>/);
  assert.match(functions.content, /<h3 class="function-detail-title"><i class="site-icon icon--functions function-detail-icon" data-lucide="square-function"[^>]*><\/i><span>&lt;Calculate&gt;<\/span><\/h3>/);
  assert.match(functions.content, /<p data-function-description[^>]*>Calculate &lt;values&gt;<\/p>/);
  assert.doesNotMatch(functions.content, /class="function-description"/);
  assert.doesNotMatch(functions.content, /function-kind-graphic|Function kind:/);
  assert.doesNotMatch(functions.content, /Operation diagram/);
  assert.match(functions.content, /&lt;script&gt;/);
  assert.match(functions.content, /DataFrame/);
  assert.match(functions.content, /<h3 class="function-detail-title">[^]*?<span>&lt;Calculate&gt;<\/span><\/h3>/);
  assert.doesNotMatch(functions.content, /<p class="mt-1 font-mono text-xs text-slate-500">calculate<\/p>/);
  const functionMetadataData = sampleData();
  functionMetadataData.catalogs.function_groups.Uncategorized.calculate.doc.body = "Equal key sets use a full join, preserving either observation scope. A\nstrict subset uses a left join.\n\nMore <details>.";
  functionMetadataData.catalogs.function_groups.Uncategorized.calculate.doc.returns = "Calculated <values>.";
  functionMetadataData.catalogs.function_groups.Uncategorized.calculate.doc.raises = [
    { type: "ValueError", description: "Invalid <value>." },
    { type: "RuntimeError", description: null },
  ];
  const functionMetadata = renderCatalog(functionMetadataData, "functions").content;
  const functionArticle = functionMetadata.slice(functionMetadata.indexOf('<article id="function-calculate"'));
  assert.match(functionArticle, /<p data-function-description[^>]*>Calculate &lt;values&gt;<\/p>\s*<div class="function-description"><p>Equal key sets use a full join, preserving either observation scope\. A\nstrict subset uses a left join\.<\/p><p>More &lt;details&gt;\.<\/p><\/div>/);
  const emptyDescriptionData = sampleData();
  emptyDescriptionData.catalogs.function_groups.Uncategorized.calculate.doc.body = " \n ";
  assert.doesNotMatch(renderCatalog(emptyDescriptionData, "functions").content, /class="function-description"/);
  assert.match(functionArticle, /<section class="function-metadata-entry" aria-label="Returns">\s*<h3 class="ui-section-title profile-detail-subheading">[^]*?data-lucide="arrow-right"[^]*?<span>Returns<\/span><\/h3>\s*<div class="function-metadata-card function-detail-box">\s*<p class="function-return-type">DataFrame<\/p>\s*<p class="function-metadata-description">Calculated &lt;values&gt;\.<\/p>/);
  assert.doesNotMatch(functionArticle.match(/<section class="function-metadata-entry" aria-label="Returns">[^]*?<\/section>/)[0], /data-type-label-icon|data-lucide="table-2"/);
  functionMetadataData.catalogs.function_groups.Uncategorized.calculate.return_type = "list<value>";
  assert.match(renderCatalog(functionMetadataData, "functions").content, /<p class="function-return-type">list&lt;value&gt;<\/p>/);
  assert.match(functionArticle, /<section class="function-metadata-entry" aria-label="Error handling">\s*<h3 class="ui-section-title profile-detail-subheading">[^]*?data-lucide="triangle-alert"[^]*?<span>Error handling<\/span><\/h3>\s*<div class="function-metadata-card function-detail-box">[^]*?<span class="function-error-type">ValueError<\/span><p class="function-metadata-description">Invalid &lt;value&gt;\.<\/p>/);
  assert.match(functionArticle, /<li><span class="function-error-type">RuntimeError<\/span><\/li>/);
  assert.match(functionArticle, /<section class="function-source" aria-label="Source">[^]*?data-lucide="code-xml"[^]*?<span>Source<\/span>[^]*?<dt>[^]*?data-lucide="package"[^]*?<span>Package<\/span><\/dt><dd><code>example<\/code><\/dd>[^]*?<dt>[^]*?data-lucide="file-code-2"[^]*?<span>Module<\/span><\/dt><dd><code>example<\/code><\/dd>[^]*?<dt>[^]*?data-lucide="square-function"[^]*?<span>Function<\/span><\/dt><dd><code>calculate<\/code>/);
  assert.match(functionArticle, /<dt>[^]*?data-lucide="map-pin"[^]*?<span>Origin<\/span><\/dt><dd><code>Unknown<\/code><\/dd>/);
  assert.match(functionArticle, /<pre class="function-detail-box mt-3 min-h-40/);
  assert.match(functionArticle, /aria-label="Function usage"[^]*?Used by operators[^]*?<li class="function-usage-item function-detail-box">[^]*?href="\?view=profiles#profile-readings">Readings<\/a>[^]*?href="\?view=profiles#operator-readings-calculate">Calculate<\/a>/);
  assert.doesNotMatch(functionArticle, /<h3 class="ui-section-title">Raises<\/h3>/);
  const escapeFunctionData = sampleData();
  escapeFunctionData.catalogs.configuration.profiles.readings.assembly.calculate.kind = "escape";
  const escapeFunction = renderCatalog(escapeFunctionData, "functions").content;
  assert.match(escapeFunction, /data-lucide="square-function"[^>]*><\/i><span>&lt;Calculate&gt;<\/span>/);
  assert.doesNotMatch(escapeFunction, /Function kind:|Escape kind|function-kind-graphic/);
  assert.doesNotMatch(escapeFunction, /Uncontrolled external effect\. Declared feature dependencies do not materialize outputs; return values are ignored\./);
  assert.match(escapeFunction, /aria-label="Function usage"[^]*?href="\?view=profiles#profile-readings">Readings<\/a>[^]*?href="\?view=profiles#operator-readings-calculate">Calculate<\/a>/);
  assert.doesNotMatch(escapeFunction, /escape-operator-card/);
  const functionOverview = functions.content.slice(0, functions.content.indexOf('<div class="space-y-8">'));
  assert.doesNotMatch(functionOverview, /data-stat=/);
  assert.doesNotMatch(functionOverview, /<h2[^>]*>Functions overview<\/h2>/);
  assert.match(functionOverview, /Functions by category/);
  assert.match(functionOverview, /data-category="Uncategorized"/);
  const categorizedFunctions = sampleData();
  categorizedFunctions.catalogs.function_groups = {
    "data_loading": { calculate: categorizedFunctions.catalogs.function_groups.Uncategorized.calculate },
  };
  categorizedFunctions.catalogs.summary.function_count = 1;
  const categorizedCatalog = renderCatalog(categorizedFunctions, "functions");
  const categorizedOverview = categorizedCatalog.content.slice(0, categorizedCatalog.content.indexOf('<div class="space-y-8">'));
  assert.match(categorizedOverview, /data-category="data_loading"[^]*?>Data Loading</);
  assert.match(categorizedCatalog.context, /context-group-label"><span>Data Loading<\/span>/);
  assert.match(categorizedCatalog.content, /href="#functions-data_loading"/);
  assert.match(functionOverview, /Functions by return type/);
  assert.match(functionOverview, /data-category="DataFrame" data-count="1"[^]*?icon--return-arrow[^>]*data-lucide="arrow-right"[^]*?class="data-type-label-text">DataFrame/);
  const returnTypeChart = functionOverview.slice(functionOverview.indexOf("Functions by return type"));
  assert.doesNotMatch(returnTypeChart, /data-lucide="table-2"/);
  const returnTypeData = sampleData();
  returnTypeData.catalogs.function_groups.Uncategorized.numeric = { return_type: "float" };
  returnTypeData.catalogs.function_groups.Other = { unknown: {} };
  const returnTypeOverview = renderCatalog(returnTypeData, "functions").content;
  const typedReturnOverview = returnTypeOverview.slice(0, returnTypeOverview.indexOf('<div class="space-y-8">'));
  assert.match(typedReturnOverview, /data-category="float" data-count="1"[^]*?data-lucide="arrow-right"[^]*?class="data-type-label-text">float/);
  assert.match(returnTypeOverview, /data-category="unspecified" data-count="1"/);
  assert.doesNotMatch(typedReturnOverview.slice(typedReturnOverview.indexOf("Functions by return type")), /data-lucide="(?:hash|table-2)"/);
  assert.match(functions.context, /href="#function-calculate"[^]*?data-lucide="square-function"/);
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
  assert.match(profileCatalog.context, /href="#overview"[^]*?>Overview/);
  assert.equal((profiles.match(/class="profile-summary-card"/g) || []).length, 2);
  assert.match(profiles, /href="#profile-readings"[^]*?class="profile-summary-size"><strong>1<\/strong><i class="site-icon icon--operators profile-summary-operator-icon" data-lucide="sigma"/);
  assert.match(profiles, /href="#profile-daily"[^]*?class="profile-summary-size"><strong>3<\/strong><i class="site-icon icon--operators profile-summary-operator-icon" data-lucide="sigma"/);
  const profileOverview = profiles.slice(0, profiles.indexOf('<div class="space-y-8">'));
  assert.match(profileOverview, /profile-summary-grain-path" aria-label="Machine dimension at machine resolution"[^]*?<span class="profile-summary-grain-badge profile-summary-grain-resolution">[^]*?icon--resolutions profile-summary-grain-icon" data-lucide="scan-square"[^]*?<code>machine<\/code><\/span>/);
  assert.doesNotMatch(profileOverview, /profile-summary-grain-relation|profile-summary-grain-dimension/);
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
  assert.match(profiles, /<h4 class="profile-grain-dimension-name"><i class="site-icon icon--dimensions profile-detail-icon" data-lucide="axis-3d" aria-hidden="true"><\/i><span>Machine<\/span><\/h4>[^]*?<ul aria-label="Resolution hierarchy" class="dimension-resolution-tree">[^]*?<li data-resolution-id="machine" data-parent-resolution="">\s*<article class="dimension-resolution-card profile-resolution-highlight">/);
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

test("function examples retain multiline content, order and HTML escaping", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  data.catalogs.function_groups.Uncategorized.calculate.doc.examples = [
    'frame = make_frame(\n    "<input>"\n)\nresult = calculate(frame)\n[1, 2]',
    'print("<second>")',
  ];

  const html = renderCatalog(data, "functions").content;
  const examples = [...html.matchAll(/<code class="language-python">([^]*?)<\/code>/g)]
    .map(match => match[1]);
  assert.deepEqual(examples, [
    'frame = make_frame(\n    &quot;&lt;input&gt;&quot;\n)\nresult = calculate(frame)\n[1, 2]',
    'print(&quot;&lt;second&gt;&quot;)',
  ]);
  const article = html.slice(html.indexOf('<article id="function-calculate"'));
  assert.equal((article.match(/<section class="function-example">/g) || []).length, 2);
  assert.ok(article.indexOf("Example 2") < article.indexOf('class="function-origin-grid"'));
  assert.match(article, /class="function-origin-grid"[^]*?class="function-source"/);
  assert.doesNotMatch(article, /class="function-kind-graphic/);
  assert.ok(article.indexOf("Arguments") < article.indexOf('class="function-metadata-grid"'));
  assert.doesNotMatch(article, /lg:grid-cols-\[minmax/);
});

test("function source and operator usage handle qualified, missing and escaped values", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const data = sampleData();
  const fn = data.catalogs.function_groups.Uncategorized.calculate;
  fn.entrypoint = "pump.<package>.analytics:Class.method";
  fn.source_origin = "third_party";
  fn.source_distribution = "library <unsafe>";
  fn.signature_validation_disabled = true;
  fn.doc.raises = [{ type: "ValueError", description: "Invalid." }];
  const assembly = data.catalogs.configuration.profiles.readings.assembly;
  assembly.calculate.name = "Calculate <values>";
  assembly.calculate.interface.outputs = [];
  assembly.merge_values = { compute: { function: "other" }, merge: { function: "calculate" },
    interface: { inputs: [], outputs: [] } };
  fn.operator_usages.push({
    profile: "readings", operator: "merge_values", role: "merge",
    execution_form: "compute + merge", grain_relationships: [],
  });

  const html = renderCatalog(data, "functions").content;
  const article = html.slice(html.indexOf('<article id="function-calculate"'));
  assert.match(article, /<dt>[^]*?data-lucide="package"[^]*?<span>Package<\/span><\/dt><dd><code>pump<\/code><\/dd>/);
  assert.match(article, /<dt>[^]*?data-lucide="map-pin"[^]*?<span>Origin<\/span><\/dt><dd><code>Third-party \(library &lt;unsafe&gt;\)<\/code><\/dd>/);
  assert.match(article, /<dt>[^]*?data-lucide="file-code-2"[^]*?<span>Module<\/span><\/dt><dd><code>pump\.&lt;package&gt;\.analytics<\/code><\/dd>/);
  assert.match(article, /<dt>[^]*?data-lucide="square-function"[^]*?<span>Function<\/span><\/dt><dd><code>Class\.method<\/code><\/dd>/);
  assert.match(article, /Python signature validation disabled/);
  assert.match(article, /operator-readings-calculate">Calculate &lt;values&gt;<\/a>/);
  assert.match(article, /operator-readings-merge_values">Merge Values<\/a>/);
  assert.match(article, /class="function-metadata-grid"[^]*?aria-label="Returns"[^]*?aria-label="Error handling"/);
  assert.ok(article.indexOf('aria-label="Error handling"') > article.indexOf("Arguments"));

  fn.source_origin = "project";
  assert.match(renderCatalog(data, "functions").content, /<span>Origin<\/span><\/dt><dd><code>Project source code<\/code><\/dd>/);

  delete fn.entrypoint;
  fn.signature_validation_disabled = false;
  fn.return_type = null;
  fn.doc.raises = [];
  assembly.calculate.compute.function = "other";
  delete assembly.merge_values.merge;
  fn.operator_usages = [];
  const empty = renderCatalog(data, "functions").content;
  assert.doesNotMatch(empty, /class="function-source"/);
  assert.match(empty, /class="function-return-type">dataframe<\/p>/);
  assert.match(empty, /Not used by any operator/);
});

test("merge phases expose their invocation metadata and owning operator", async () => {
  const { renderCatalog } = await moduleAt("catalogs/catalog_renderer.js");
  const { lineage } = await moduleAt("rendering/page_renderer.js");
  const data = sampleData();
  const merge = {
    invocation_id: "invocation:merge:join:readings:calculate",
    operator_id: "calculate",
    role: "merge",
    result: "target",
    execution_form: "compute + merge",
    binding_roles: ["compute", "merge"],
    grain_relationships: [],
    function_returns: "dataframe",
    function: "join",
    title: "Join results",
    function_label: "Join results",
    merge_dataset: "readings",
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
    depends_on_invocations: [{ id: "read", function: "Read values", role: "compute" }],
    args: {
      target: { value: "readings", type: { function: "dataframe | null" } },
      fragment: { value: "$operators.calculate.fragment", type: { function: "dataframe" } },
      dataset_keys: { value: ["id"], type: { function: "array[string]" } },
    },
    returns: { type: { engine: "DataFrame" } },
  };
  data.stages = [{ stage: 1, steps: [merge] }];
  data.graphs.invocation_lineage = {
    nodes: [{
      id: merge.invocation_id,
      role: "merge",
      result: "target",
      function_returns: "dataframe",
      execution_form: "compute + merge",
      binding_roles: ["compute", "merge"],
      grain_relationships: [],
      function_name: merge.function_label,
      operator_id: merge.operator_id,
      profile_id: "readings",
      merge_dataset: merge.merge_dataset,
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
    args: { dataset: "$profiles.@.dataset", fragment: "$operators.@.fragment", dataset_keys: ["id"] },
  };
  data.catalogs.configuration.profiles.readings.assembly.calculate.execution_form = "compute + merge";
  data.catalogs.configuration.profiles.readings.assembly.calculate.binding_roles = ["compute", "merge"];
  data.catalogs.configuration.functions.join = { name: "Join results", returns: "dataframe", category: "Joining" };
  data.catalogs.function_groups.Joining = { join: data.catalogs.configuration.functions.join };

  const stages = renderCatalog(data, "stages").content;
  const profiles = renderCatalog(data, "profiles").content;
  const topology = lineage(data, true).content;
  assert.match(stages, /data-role="merge"/);
  assert.match(stages, /Merge dataset/);
  assert.match(stages, /Fragment source/);
  assert.match(stages, /Merge keys/);
  assert.match(profiles, /id="operator-readings-calculate"/);
  assert.match(profiles, /data-execution-form="compute \+ merge"/);
  assert.match(profiles, /data-lucide="git-merge"/);
  assert.match(profiles, /The resulting fragment is merged into this profile&#39;s dataset\. Grain relationships:/);
  assert.match(topology, /"role":"merge"/);
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
    assert.match(html, /aria-label="Open graph legend and node details"/);
    assert.doesNotMatch(html, /Legend &amp; details|<span>Open graph legend and node details<\/span>/);
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
  assert.match(html, /href="#overview"/);
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
  config.functions.aggregate = { name: "Maximum <reading>", returns: "dataframe" };
  config.functions.external = { returns: "any" };
  config.profiles.readings.assembly.aggregate = {
    operator_label: "Collapse",
    execution_form: "compute",
    binding_roles: ["compute"],
    grain_relationships: [{ source_profile: "source", relationship: "collapse" }],
    produces_target_features: true,
    compute: { function: "aggregate", args: {
      dataset: "$profiles.source.dataset",
      options: { method: "<max>" },
      health_features: ["$features.bearing_temperature_delta", "$features.pressure_flow_efficiency"],
    } },
    interface: { inputs: ["$features.raw"], outputs: ["$features.value"] },
  };
  config.profiles.readings.assembly.external = {
    operator_label: "Escape",
    execution_form: "compute",
    binding_roles: ["compute"],
    grain_relationships: [],
    produces_target_features: false,
    compute: { function: "external", args: {} },
    interface: { inputs: [], outputs: ["$features.<logical>"] },
  };
  data.stages[0].steps.push({
    profile: "readings",
    operator_id: "aggregate",
    role: "compute",
    args: {
      dataset: { value: "$profiles.source.dataset", type: { engine: "DataFrame" } },
      options: { value: { method: "<max>" }, type: { function: "dict" } },
      health_features: {
        value: ["bearing_temperature_delta", "pressure_flow_efficiency"],
        type: { function: "array[string]" },
      },
    },
  });
  const html = renderCatalog(data, "profiles").content;
  assert.ok(html.indexOf("<span>Produced schema</span></h3>") < html.indexOf("<span>Assembly</span></h3>"));
  assert.match(html, /<span>Produced schema<\/span><\/h3><div class="ui-table-scroll profile-schema-scroll/);
  assert.match(html, /profile-detail-subheading[^>]*>[^]*?<span>Assembly<\/span><\/h3>/);
  assert.doesNotMatch(html, /profile-operator-kicker|>OPERATION</);
  assert.match(html, /<div class="profile-operator-list">/);
  assert.doesNotMatch(html, /<div class="profile-operator">/);
  assert.match(html, /data-profile-operator="aggregate" data-execution-form="compute"/);
  assert.match(html, /href="\?view=functions#function-aggregate">Maximum &lt;reading&gt;<\/a>/);
  assert.match(html, /Input features<\/dt><dd><code>raw<\/code>/);
  assert.match(html, /Output features<\/dt><dd><code>&lt;Value&gt;<\/code>/);
  assert.match(html, /<details class="profile-operator-bindings profile-operator-bindings-inline"><summary>Arguments<\/summary>/);
  assert.match(html, /<th scope="col">Argument<\/th><th scope="col">Spec value<\/th><th scope="col">Resolved value<\/th>/);
  assert.match(html, /<span class="ui-badge profile-operator-argument-value"><code class="language-json">\$profiles\.source\.dataset<\/code><\/span>/);
  assert.match(html, /class="ui-badge profile-operator-argument-value"><code class="language-json">\[\n\s+\$features\.bearing_temperature_delta,\n\s+\$features\.pressure_flow_efficiency\n\s*\]<\/code><\/span>/);
  const aggregateTable = html.match(/<article id="operator-readings-aggregate"[^]*?<table class="ui-table">([^]*?)<\/table>/)[1];
  const optionsRow = [...aggregateTable.matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
    .map(([, row]) => row).find(row => row.includes("<span>options</span>"));
  assert.match(optionsRow, /<\/th>\s*<td><code class="language-json">\{\n\s+&quot;method&quot;: &quot;&lt;max&gt;&quot;\n\s*\}<\/code>/);
  assert.match(html, /This value will be bound only during the engine execution\./);
  const datasetRow = [...aggregateTable.matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
    .map(([, row]) => row).find(row => row.includes("<span>dataset</span>"));
  assert.match(datasetRow, /<span class="ui-badge profile-operator-argument-value"><span class="profile-operator-engine-bind"[\s\S]*?<\/span><code class="language-json">\$profiles\.source\.dataset<\/code><\/span>/);
  assert.doesNotMatch(datasetRow, /<\/span><span class="profile-operator-engine-bind"/);
  assert.doesNotMatch(html, /Group by grain keys:|ui-badge--neutral">collapse/);
  assert.match(html, /Output features \(logical\)<\/dt><dd><code>&lt;logical&gt;<\/code>/);
  assert.match(html, /None declared/);
  assert.match(html, /outputs are not materialized as dataframe columns/);
  assert.match(html, /data-profile-operator="calculate" data-execution-form="compute"/);
  const operator = html.match(/<article id="operator-readings-aggregate"[^]*?<\/article>/)[0];
  assert.match(operator, /profile-operator-header[^]*profile-operator-contract[^]*profile-operator-compute/);
  assert.match(operator, /class="site-icon icon--functions profile-operator-function-icon" data-lucide="square-function"/);
  assert.doesNotMatch(operator, /profile-operator-flow-node/);
  assert.ok(operator.indexOf("Input features") < operator.indexOf("profile-operator-compute"));
  assert.ok(operator.indexOf("profile-operator-compute") < operator.indexOf("Output features"));
  assert.ok(!html.includes("<max>"));
});

test("feature catalog excludes grain keys, unused declarations and duplicate outputs", async () => {
  const { features, schemaColumns } = await moduleAt("catalogs/catalog_renderer.js");
  const config = sampleData().catalogs.configuration;
  const profile = config.profiles.readings;
  profile.features.unused = { type: "string" };
  profile.assembly.calculate.interface.outputs.push("$features.id", "$features.value");
  assert.deepEqual(features(config).map(item => item.featureId), ["value"]);
  assert.deepEqual(schemaColumns(config, profile).map(column => column.role),
    ["ID", "Feature", "Feature"]);
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
    /data-resolution-id="plant"[^]*?<ul class="dimension-resolution-children"[^>]*><li id="dimension-resolution-machine-production_line" data-resolution-id="production_line"[^]*?<ul class="dimension-resolution-children"[^>]*><li id="dimension-resolution-machine-machine" data-resolution-id="machine"/,
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
  const plan = planOverview(data);
  assert.match(plan, /Invocations by binding role/);
  assert.match(plan, /Invocations by stage/);
  assert.doesNotMatch(plan, /Max parallel invocations|data-stat=/);
});

test("lineage views expose original canvases, controls and script-safe graph data", async () => {
  const { lineage } = await moduleAt("rendering/page_renderer.js");
  const feature = lineage(sampleData(), false);
  assert.match(feature.content, /id="lineage-2d"/);
  assert.match(feature.content, /id="lineage-3d"/);
  assert.match(feature.context, /data-dimension="3d"/);
  assert.match(feature.context, /id="node-details"/);
  assert.match(feature.context, /<details class="lineage-legend-panel"><summary>/);
  assert.match(feature.context, /Graph legend/);
  assert.equal((feature.context.match(/class="lineage-legend-note"/g) || []).length, 1);
  assert.match(feature.context, /Colors show profiles, not run status\. Arrows show dependencies\./);
  assert.match(feature.context, /1 profile<\/span>/);
  assert.match(feature.context, /id="operator-legend"/);
  assert.match(feature.context, /No node selected/);
  assert.ok(!feature.content.includes("</script><script>"));
  const payload = feature.content.match(/id="graph-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  assert.deepEqual(JSON.parse(payload), sampleData().graphs.feature_lineage);
  assert.match(lineage(sampleData(), true).context, /id="invocation-node-details"/);
  const topologyData = sampleData();
  topologyData.graphs.invocation_lineage.nodes = [
    { id: "first", profile_id: "readings", role: "merge" },
    { id: "second", profile_id: "readings", role: "merge" },
    { id: "third", role: "<custom>" },
  ];
  const topology = lineage(topologyData, true).context;
  assert.match(topology, /2 profiles<\/span>/);
  assert.equal((topology.match(/data-lucide="git-merge"/g) || []).length, 1);
  assert.match(topology, /&lt;custom&gt;/);
  assert.doesNotMatch(topology, /id="operator-legend"/);
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
