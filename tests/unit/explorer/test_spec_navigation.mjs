import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../../src/uptimely/explorer/app/static/js/", import.meta.url);
const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const shared = moduleUrl(await readFile(new URL("rendering/shared_markup.js", root), "utf8"));
const pages = moduleUrl((await readFile(new URL("rendering/page_renderer.js", root), "utf8"))
  .replace("./shared_markup.js", shared));
const catalog = (await readFile(new URL("catalogs/catalog_renderer.js", root), "utf8"))
  .replace("../rendering/shared_markup.js", shared)
  .replace("../rendering/page_renderer.js", pages);
const { catalogContext, renderCatalog, schemaColumns, stageCards } = await import(moduleUrl(catalog));
const { Router } = await import(moduleUrl(
  await readFile(new URL("application/history_router.js", root), "utf8"),
));
const {
  badge, dataTypeIcon, dataTypeIconName, distribution, heading, icon, kindIcon, shell, typedName,
  statistic, contextHeader,
} = await import(shared);
const { dashboard, lineage, planOverview } = await import(pages);

test("Plan Overview uses the dashboard grid icon in navigation and title", () => {
  const markup = shell({ project: {}, scope: {} }, "plan", "", "");
  assert.match(markup, /href="\?view=plan"[^>]*>[\s\S]*?data-lucide="layout-grid"[\s\S]*?Overview/);
  const content = planOverview({
    plan: { function_kind_counts: [], invocation_count: 0, stage_count: 0 },
    stages: [],
  });
  assert.match(content, /<h1[^>]*>[\s\S]*?data-lucide="layout-grid"[\s\S]*?<span>Overview<\/span><\/h1>/);
});

test("Lineage uses the horizontal flow diagram icon", () => {
  assert.match(icon("feature-lineage"), /data-lucide="diagram-flow-horizontal"/);
});

test("Topology uses the right arrow layout icon", () => {
  assert.match(icon("invocation-lineage"), /data-lucide="layout-arrow-right"/);
});

test("resolutions use the scan square icon", () => {
  assert.match(icon("resolutions"), /data-lucide="scan-square"/);
});

test("vectorize uses the table properties icon", () => {
  assert.match(kindIcon("vectorize"), /data-lucide="table-properties"/);
});

test("data type icons normalize common aliases and composed types", () => {
  for (const [type, name] of [
    ["Float64", "hash"], ["uint32", "hash"], ["array[string]", "brackets"],
    ["object{str: float}", "braces"], ["pandas.DataFrame", "table-2"],
    ["boolean", "toggle-left"], ["datetime64[ns]", "calendar-clock"],
  ]) {
    assert.equal(dataTypeIconName(type), name, type);
    assert.match(dataTypeIcon(type, "type-icon"), new RegExp(`data-lucide="${name}"`), type);
  }
  assert.equal(dataTypeIconName("unspecified"), null);
});

test("typed names put the icon before the name without visible type text", () => {
  const markup = typedName("<reading>", "array[string]");
  assert.match(markup, /title="array\[string\]" aria-label="&lt;reading&gt; \(array\[string\]\)"/);
  assert.match(markup, /data-lucide="brackets"[^>]*><\/i><span>&lt;reading&gt;<\/span>/);
  assert.doesNotMatch(markup, />array\[string\]</);
  assert.match(typedName("unknown", null), /data-lucide="braces"/);
});

test("function context uses shared category labels and flat icon links", () => {
  const context = catalogContext({ catalogs: { function_groups: {
    read: { load: { name: "Load data" }, fetch: { name: "Fetch data" } },
    vectorize: { score: { name: "Score" } },
    write: {},
  } } }, "functions");
  assert.match(context, /context-group-label"><span>Read<\/span><span class="context-link-count">2<\/span>/);
  assert.match(context, /context-group-label"><span>Vectorize<\/span><span class="context-link-count">1<\/span>/);
  for (const id of ["load", "fetch", "score"]) {
    assert.match(context, new RegExp(`href="#function-${id}"[\\s\\S]*?data-lucide="square-function"`));
  }
  assert.doesNotMatch(context, /context-sublinks|href="#functions-|>Write<\/span>/);
});

test("produced schema is a table listing declared columns vertically with their metadata", () => {
  const { content } = renderCatalog({
    catalogs: {
      summary: {},
      configuration: { dimensions: {}, functions: {}, profiles: {
        readings: { name: "Readings", grain: [], assembly: {}, features: {
          temperature: { name: "Temperature", type: "float", unit: "C" },
          label: { type: "string" },
        } },
      } },
    },
  }, "profiles");
  assert.match(content, /profile-detail-subheading[^>]*>[\s\S]*?<span>Produced schema<\/span><\/h3>/);
  assert.doesNotMatch(content, /Produced dataset/);
  const table = content.match(/<table data-dataset-schema="readings"[\s\S]*?<\/table>/)[0];
  assert.equal((table.match(/scope="col"/g) || []).length, 4);
  assert.match(table, />Producing operator<\/th>/);
  assert.match(table, /None declared/);
  assert.equal((table.match(/scope="row"/g) || []).length, 2);
  assert.match(table, /data-schema-column="temperature"[\s\S]*?data-lucide="hash"[\s\S]*?<span>temperature<\/span>[\s\S]*?Feature[\s\S]*?>C<\/td>/);
  assert.doesNotMatch(table, />Data type<|>float<|>string<|data-type-label-text|Temperature/);
  assert.match(table, /<colgroup>/);
  assert.match(table, /data-schema-column="label"[\s\S]*?data-lucide="case-sensitive"[\s\S]*?<span>label<\/span>[\s\S]*?—<\/td>/);
});

test("schema columns include every producing operator including grain and vectorized features", () => {
  const config = {
    dimensions: { machine: { resolutions: { unit: { key: "machine_id" } } } },
    functions: { read: { kind: "read" }, compute: { kind: "vectorize" } },
  };
  const profile = {
    grain: [{ dimension: "machine", resolution: "unit" }],
    features: { machine_id: {}, temperature: {}, score: {}, orphan: {} },
    assembly: {
      load: { compute: { function: "read" }, interface: { outputs: ["$features.machine_id", "$features.temperature"] } },
      calculate: { compute: { function: "compute" }, interface: { outputs: ["$features.score", "$features.score"] } },
      revise: { compute: { function: "compute" }, interface: { outputs: ["$features.score"] } },
    },
  };
  const columns = schemaColumns(config, profile);
  assert.deepEqual(columns.map(({ id, operators }) => [id, operators]), [
    ["machine_id", ["load"]], ["temperature", ["load"]],
    ["score", ["calculate", "revise"]], ["orphan", []],
  ]);
});

test("profile details show every declared operator in order including vectorized operator", () => {
  const kinds = ["read", "vectorize", "expand", "vectorize", "collapse", "escape", "write"];
  const assembly = Object.fromEntries(kinds.map((kind, index) => [`operator_${index}`, {
    compute: { function: kind, args: { output: `$outputs.value_${index}` } },
    interface: { inputs: [], outputs: [] },
  }]));
  const configuration = {
    dimensions: {},
    functions: Object.fromEntries(kinds.map(kind => [kind, { name: `${kind} function`, kind }])),
    profiles: { telemetry: { grain: [], features: {}, assembly } },
  };
  const stages = [{ steps: Object.keys(assembly).map((operator_id, index) => ({
    profile: "telemetry", operator_id, phase: "compute",
    args: { output: { type: { function: "string" }, value: `resolved_${index}` } },
  })) }];
  const render = () => renderCatalog({ catalogs: { summary: {}, configuration }, stages }, "profiles").content;
  const content = render();
  assert.deepEqual([...content.matchAll(/data-profile-operator="([^"]+)"/g)].map(match => match[1]),
    Object.keys(assembly));
  assert.equal((content.match(/data-operator-kind="vectorize"/g) || []).length, 2);
  assert.match(content, /<summary>Resolved arguments<\/summary>/);
  assert.match(content, /class="language-json">&quot;resolved_1&quot;<\/code>/);
  assert.match(content, /href="\?view=functions#function-vectorize">vectorize function/);
  assert.doesNotMatch(content, /\$outputs\.value_1/);

  configuration.profiles.telemetry.assembly = { calculate: assembly.operator_1 };
  const vectorizedOnly = render();
  assert.match(vectorizedOnly, /profile-detail-subheading[^>]*>[\s\S]*?<span>Assembly<\/span><\/h3>/);
  assert.match(vectorizedOnly, /profile-operator-kicker">OPERATION<\/span>/);
  assert.match(vectorizedOnly, /profile-operator-list/);
  assert.doesNotMatch(vectorizedOnly, /<div class="profile-operator">/);
  assert.match(vectorizedOnly, /data-profile-operator="calculate" data-operator-kind="vectorize"/);
});

test("profile grain uses compact dimension and resolution badges", () => {
  const { content } = renderCatalog({ catalogs: { summary: {}, configuration: {
    functions: {}, dimensions: { machine: { name: "Machine", resolutions: {
      unit: { key: "machine_id", type: "string" },
    } } },
    profiles: { sample: { grain: [{ dimension: "machine", resolution: "unit" }],
      features: { machine_id: {} }, assembly: {} } },
  } } }, "profiles");
  assert.match(content, /A profile is identified by its grain\./);
  const grain = content.match(/<div class="profile-detail-grain">[\s\S]*?<\/ul>/)[0];
  assert.match(grain, /profile-summary-grain-badge profile-summary-grain-resolution[\s\S]*?<code>unit<\/code>/);
  assert.match(grain, /profile-summary-grain-relation" data-lucide="at-sign"/);
  assert.match(grain, /profile-summary-grain-badge profile-summary-grain-dimension[\s\S]*?<strong>Machine<\/strong>/);
  assert.doesNotMatch(grain, /Data key|Data type|machine_id/);
});

test("feature and function type displays use matching data type icons", () => {
  const data = { catalogs: {
    summary: {
      feature_count: 1, vectorized_feature_count: 0,
      feature_buckets: { input: 1, intermediate: 0, output: 0 }, function_count: 1,
    },
    configuration: {
      dimensions: {},
      functions: { load: { kind: "read", name: "Load" } },
      profiles: { telemetry: {
        grain: [], features: { temperature: { type: "float64" } },
        assembly: { load: {
          compute: { function: "load" },
          interface: { outputs: ["$features.temperature"] },
        } },
      } },
    },
    function_groups: { read: { load: {
      name: "Load", kind: "read", args: {
        source: { type: "dataframe" }, path: { type: "string" },
      },
      doc: { params: { source: "Input table", path: "Source location" } },
      return_type: "pandas.DataFrame",
    } } },
  } };
  const { content: featureContent, context: featureContext } = renderCatalog(data, "features");
  assert.match(featureContent, /data-lucide="hash"[^>]*data-type="float64"/);
  const featureCard = featureContent.match(/<article id="feature-telemetry-temperature"[\s\S]*?<\/article>/)[0];
  assert.doesNotMatch(featureCard, />Data type<|>float64</);
  assert.match(featureContent, /data-category="float64" data-count="1"/);
  assert.match(featureContent, /data-lucide="hash"[^>]*><\/i><span>temperature<\/span>/);
  assert.match(featureContext, /href="#feature-telemetry-temperature"[\s\S]*?data-lucide="hash"/);
  const featureLink = featureContext.match(/<a href="#feature-telemetry-temperature">[\s\S]*?<\/a>/)[0];
  assert.doesNotMatch(featureLink, /data-lucide="sigma"/);
  const functionContent = renderCatalog(data, "functions").content;
  assert.match(functionContent, /data-lucide="table-2"[^>]*data-type="dataframe"/);
  assert.match(functionContent, /data-lucide="table-2"[^>]*data-type="pandas\.DataFrame"/);
  const argumentTable = functionContent.match(/<table class="ui-table function-arguments-table">[\s\S]*?<\/table>/)[0];
  assert.match(argumentTable, /<th scope="col">Argument<\/th><th scope="col">Description<\/th>/);
  assert.match(argumentTable, /data-lucide="table-2"[^>]*><\/i><span>source<\/span>[\s\S]*<td>Input table<\/td>/);
  assert.match(argumentTable, /data-lucide="case-sensitive"[^>]*><\/i><span>path<\/span>[\s\S]*<td>Source location<\/td>/);
  assert.doesNotMatch(argumentTable, />Data type<|>dataframe<|>string<|data-type-label-text/);
});

test("dimension details distinguish the dimension from its nested resolution levels", () => {
  const { content } = renderCatalog({
    catalogs: {
      summary: { dimension_count: 1 },
      configuration: { dimensions: {
        location: { name: "Location", resolutions: {
          country: { key: "country_id", type: "string" },
          city: { key: "city_id", type: "string", parent: "country" },
          site: { key: "site_id", type: "integer", parent: "city" },
        } },
      } },
    },
  }, "dimensions");
  assert.match(content, /data-dimension-label[^>]*hidden>Dimension<\/p>/);
  assert.doesNotMatch(content, /<p[^>]*>location<\/p>/);
  assert.match(content, /aria-label="Resolution levels"/);
  assert.match(content, /Resolution levels, from parent to child\./);
  for (const id of ["country", "city"]) {
    assert.match(content, new RegExp(`<h3 class="dimension-resolution-id"><span class="typed-name"[^>]*>[\\s\\S]*?data-lucide="case-sensitive"[^>]*><\\/i><span>${id}</span>`));
  }
  assert.match(content, /<span class="typed-name" title="integer" aria-label="site \(integer\)"><i data-lucide="hash"[^>]*><\/i><span>site<\/span>/);
  const hierarchy = content.match(/<ul aria-label="Resolution hierarchy"[\s\S]*?<\/section>/)[0];
  assert.doesNotMatch(hierarchy, /country_id|city_id|site_id|data-type-label-text|>string<|>integer</);
  assert.match(content, /data-resolution-id="city" data-parent-resolution="country"/);
  assert.match(content, /data-resolution-id="site" data-parent-resolution="city"/);
  assert.equal((content.match(/class="dimension-resolution-children"/g) || []).length, 2);
  assert.doesNotMatch(content, /Parent resolution:|Top-level resolution|dimension-resolution-level|dimension-resolution-fields/);
});

test("Features overview shows role and data type charts without summary cards", () => {
  const data = {
    catalogs: {
      configuration: {
        functions: { load: {} },
        profiles: {
          readings: {
            features: { temperature: { type: "float" }, label: { type: "string" } },
            grain: [],
            assembly: { load: {
              compute: { function: "load" },
              interface: { outputs: ["$features.temperature", "$features.label"] },
            } },
          },
        },
      },
      summary: {
        feature_buckets: { input: 3, intermediate: 2, output: 1 },
        feature_count: 6, vectorized_feature_count: 2,
      },
    },
  };
  const { content } = renderCatalog(data, "features");
  assert.match(content, /data-section-count class="ui-badge">6 features<\/span>/);
  assert.match(content, /aria-label="Features overview"/);
  assert.doesNotMatch(content, /<h2[^>]*>Features overview<\/h2>|data-stat=/);
  assert.match(content, /data-category="input" data-count="3"/);
  assert.match(content, /data-category="intermediate" data-count="2"/);
  assert.match(content, /data-category="output" data-count="1"/);
  const roleChart = content.match(/<h3>Features by role<\/h3>[\s\S]*?<\/section>/)[0];
  assert.doesNotMatch(roleChart, /ui-panel-meta|total 6/);
  assert.match(roleChart, /icon--input h-4 w-4 shrink-0" data-lucide="arrow-right-to-line"/);
  assert.match(roleChart, /icon--intermediate h-4 w-4 shrink-0" data-lucide="workflow"/);
  assert.match(roleChart, /icon--output h-4 w-4 shrink-0" data-lucide="arrow-right-from-line"/);
  assert.match(roleChart, /class="ui-chart-tooltip" tabindex="0" data-tooltip="Inputs are source features counted per profile\. Intermediate features are used by another calculation; other calculated features are outputs\."/);
  assert.doesNotMatch(content, /Vectorized features: 2|Features by profile/);
  assert.match(content, /<h3>Features by data type<\/h3>/);
  assert.match(content, /data-category="float" data-count="1"/);
  assert.match(content, /data-category="string" data-count="1"/);
  assert.match(content, /<div class="catalog-charts lg:grid-cols-2">/);
});

test("catalog overview navigation uses the appropriate label and profile cards show profile size", () => {
  const data = {
    catalogs: {
      configuration: { profiles: {
        small: { name: "Small", category: "Realtime", grain: [{ dimension: "time", resolution: "day" }], features: { temperature: {} }, assembly: {
          read: { compute: { function: "calculate" }, interface: { inputs: [], outputs: [] } },
        } },
        large: { name: "Large", category: "Batch", grain: [], features: {}, assembly: {
          read: { compute: { function: "calculate" }, interface: { inputs: [], outputs: [] } },
          transform: { compute: { function: "calculate" }, interface: { inputs: [], outputs: [] } },
          write: { compute: { function: "calculate" }, interface: { inputs: [], outputs: [] } },
        } },
      }, dimensions: { time: { name: "Time", resolutions: { day: { id: "day" } } } }, functions: { calculate: { name: "Calculate", kind: "read" } } },
      summary: { feature_buckets: {}, feature_count: 0 },
      function_groups: {},
    },
    plan: { function_kind_counts: [] },
    stages: [],
  };
  const { content, context } = renderCatalog(data, "profiles");
  assert.match(context, /href="#overview"[\s\S]*?data-lucide="layout-grid"[\s\S]*?>Overview/);
  assert.match(content, /aria-label="Profiles overview"/);
  assert.match(content, /<h1[^]*?<span>Profiles<\/span><\/h1>[^]*?<p data-section-description[^>]*>A profile defines computational operators required to assemble a dataset at a specific grain\.<\/p>/);
  assert.doesNotMatch(content, /profile-summary-note/);
  assert.doesNotMatch(content, /<h2[^>]*>Profiles overview<\/h2>/);
  assert.equal((content.match(/class="profile-summary-card"/g) || []).length, 2);
  assert.match(content, /<div class="profile-summary-grain" aria-label="Profile grain">\s*<span class="profile-summary-grain-label">Grain<\/span>\s*<span class="profile-summary-grain-empty">No grain defined<\/span>/);
  assert.doesNotMatch(content, /<h3>Large<\/h3>\s*<span class="profile-summary-grain-empty">No grain defined<\/span>/);
  assert.match(content, /href="#profile-small"[\s\S]*?class="profile-summary-meter"[^]*?class="profile-summary-size"><strong>1<\/strong><span>operator<\/span>/);
  assert.match(content, /href="#profile-large"[\s\S]*?class="profile-summary-meter"[^]*?class="profile-summary-size"><strong>3<\/strong><span>operators<\/span>/);
  assert.match(content, /relative profile size/);
  assert.match(content, /profile-summary-grain-path" aria-label="Time dimension at day resolution"[^]*?<span class="profile-summary-grain-badge profile-summary-grain-resolution">[^]*?icon--resolutions profile-summary-grain-icon" data-lucide="scan-square"[^]*?<code>day<\/code><\/span>\s*<i class="profile-summary-grain-relation" data-lucide="at-sign"[^]*><\/i>\s*<span class="profile-summary-grain-badge profile-summary-grain-dimension">[^]*?icon--dimensions profile-summary-grain-icon" data-lucide="axis-3d"[^]*?<strong>Time<\/strong><\/span>/);
  assert.match(content, /profile-summary-grain-icon/);
  assert.doesNotMatch(content, /<span>Dimension<\/span>|<span>Resolution<\/span>/);
  const overview = content.slice(0, content.indexOf('<div class="space-y-8">'));
  assert.doesNotMatch(overview, /<code>small<\/code>|<code>large<\/code>|\b1 features\b/);
  assert.doesNotMatch(content, /Profiles stats|Profiles by category|data-stat=/);
});

test("catalog overviews use the shared dashboard icon and summary panels", () => {
  const data = {
    catalogs: {
      configuration: { profiles: {}, dimensions: {} },
      summary: { feature_buckets: {}, feature_count: 0 },
      function_groups: {},
    },
    plan: { function_kind_counts: [] },
    stages: [],
  };
  for (const view of ["features", "functions", "dimensions", "stages"]) {
    const { content, context } = renderCatalog(data, view);
    const title = view[0].toUpperCase() + view.slice(1);
    assert.match(context, /href="#overview"[\s\S]*?data-lucide="layout-grid"[\s\S]*?>Overview/);
    assert.match(content, new RegExp(`aria-label="${title} overview"`));
    if (view === "features") {
      assert.doesNotMatch(content, /<h2[^>]*>Features overview<\/h2>|data-stat=/);
    } else {
      assert.match(content, new RegExp(`<h2 class="ui-section-title mb-6">${title} overview</h2>`));
      assert.match(content, /class="ui-panel" data-stat=/);
    }
    assert.match(content, /class="ui-panel ui-chart"/);
    assert.doesNotMatch(content + context, />Stats| stats/);
  }
});

test("shared components escape content, omit decorative metric icons, and handle empty charts", () => {
  assert.match(badge("<role>", "green"), />&lt;role&gt;<\/span>/);
  assert.doesNotMatch(statistic("Types", 2), /data-lucide/);
  assert.match(heading("Profiles", ""), /data-section-description[^>]*hidden/);
  assert.doesNotMatch(contextHeader("Preview", "preview", "preview-context"), /<h1/);
  const chart = distribution("<Title>", [["<name>", 0, "#target"]], { total: 0 });
  assert.match(chart, /&lt;Title&gt;/);
  assert.match(chart, /href="#target"/);
  assert.match(chart, /width:0%/);
  assert.doesNotMatch(chart, /NaN|Infinity|<name>/);
  assert.match(distribution("Empty", []), /No categories to display/);
});

test("home journey matches menu sections and distinguishes saved results from animation", () => {
  const content = dashboard({
    project: { name: "Example", spec_version: 3 },
    catalogs: { summary: {} }, plan: {},
  });
  for (const title of ["Analytical model", "Execution plan", "Run results"]) {
    assert.match(content, new RegExp(`<h3>${title}</h3>`));
  }
  assert.match(content, /href="\?view=info"/);
  assert.doesNotMatch(content, /not a live execution monitor/);
});

test("topology controls use topology labels while retaining graph hooks", () => {
  const { context } = lineage({
    graphs: { invocation_lineage: {}, invocation_style: {} },
  }, true);
  assert.match(context, /aria-label="Topology context"/);
  assert.match(context, /aria-label="Topology view"/);
  assert.match(context, /id="reset-lineage"[^>]*aria-label="Reset view"[^>]*title="Reset view"[^>]*>[\s\S]*?data-lucide="scan-search"/);
  assert.match(context, /id="invocation-node-details"/);
  assert.doesNotMatch(context, /Lineage context|Reset lineage/);
  assert.doesNotMatch(context, /show-operators/);
  assert.doesNotMatch(context, /Invocation flow|legend-dependency|legend-mainframe|lineage-guide-note/);
  assert.match(context, /id="dataset-legend"/);
  assert.doesNotMatch(context, /Parallel \/ unordered/);
  assert.match(context, /id="show-full-lineage"[^>]*aria-label="Select an invocation to change highlight scope"[^>]*aria-pressed="true"[^>]*disabled/);
  assert.match(context, /id="show-full-lineage"[^>]*><i data-lucide="route" aria-hidden="true"><\/i><\/button>/);
});

test("Dataset endpoint wording and graph payload honor scoped builds", () => {
  for (const scoped of [false, true]) {
    const data = { scope: { is_scoped: scoped }, graphs: {
      invocation_lineage: { nodes: [], links: [] }, invocation_style: {},
    } };
    const { context, content } = lineage(data, true);
    assert.doesNotMatch(context, /Invocation flow/);
    const payload = JSON.parse(content.match(/id="graph-data"[^>]*>(.*?)<\/script>/)[1]);
    assert.equal(payload.is_scoped, scoped);
    assert.deepEqual(data.graphs.invocation_lineage, { nodes: [], links: [] });
  }
});

test("lineage and topology reset controls use accessible icon-only buttons", () => {
  for (const topology of [false, true]) {
    const { context } = lineage({
      graphs: { feature_lineage: {}, feature_style: {}, invocation_lineage: {}, invocation_style: {} },
    }, topology);
    const label = "Reset view";
    assert.match(context, new RegExp(`<button class="ui-button lineage-reset" id="reset-lineage" type="button" aria-label="${label}" title="${label}" aria-controls="lineage"><i[^>]*data-lucide="scan-search" aria-hidden="true"><\\/i><\\/button>`));
    const group = context.match(/<div class="lineage-buttons" role="group" aria-label="(?:Lineage|Topology) viewport">([\s\S]*?)<\/div>/)?.[1];
    assert.ok(group);
    assert.equal([...group.matchAll(/<button\b/g)].length, 3);
    assert.match(group, /data-zoom="1.25"[\s\S]*data-zoom="0.8"[\s\S]*id="reset-lineage"/);
    assert.doesNotMatch(context, />Reset (lineage|topology)</);
  }
});

test("feature lineage exposes a pressed accessible function-icon toggle beside dimension controls", () => {
  const { context } = lineage({
    graphs: { feature_lineage: {}, feature_style: {} },
  }, false);
  assert.match(context, /class="lineage-control-groups">[\s\S]*data-dimension="3d"[\s\S]*class="ui-button lineage-operator-toggle"/);
  assert.match(context, /<button class="ui-button lineage-operator-toggle" id="show-operators" type="button" aria-label="Show operators" title="Show operators" aria-pressed="true" aria-controls="lineage"><i[^>]*data-lucide="square-function" aria-hidden="true"><\/i><\/button>/);
  assert.doesNotMatch(context, /type="checkbox"|>Show operators</);
});

test("2D and 3D controls use square and box icons with preserved selection and labels", () => {
  for (const topology of [false, true]) {
    const { context } = lineage({
      graphs: { feature_lineage: {}, feature_style: {}, invocation_lineage: {}, invocation_style: {} },
    }, topology);
    for (const [dimension, name, pressed] of [["2d", "square", "true"], ["3d", "box", "false"]]) {
      const button = [...context.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)]
        .map(match => match[0]).find(markup => markup.includes(`data-dimension="${dimension}"`));
      assert.ok(button);
      assert.ok(button.includes(`title="Show ${dimension.toUpperCase()} view"`));
      assert.ok(button.includes(`aria-label="Show ${dimension.toUpperCase()} view"`));
      assert.ok(button.includes(`aria-pressed="${pressed}"`));
      assert.ok(button.includes(`aria-controls="lineage-${dimension}"`));
      assert.ok(button.includes(`data-lucide="${name}" aria-hidden="true"`));
      assert.doesNotMatch(button, />(2D|3D)<\/button>/);
    }
  }
});

test("every lineage and topology graph control has a tooltip matching its accessible label", () => {
  for (const topology of [false, true]) {
    const { context } = lineage({
      graphs: { feature_lineage: {}, feature_style: {}, invocation_lineage: {}, invocation_style: {} },
    }, topology);
    const controls = context.slice(context.indexOf('<div class="lineage-control-groups">'),
      context.indexOf('<details class="panel"'));
    const buttons = [...controls.matchAll(/<button\b[^>]*>/g)].map(match => match[0]);
    assert.equal(buttons.length, 6);
    for (const button of buttons) {
      const title = button.match(/\btitle="([^"]+)"/)?.[1];
      const label = button.match(/\baria-label="([^"]+)"/)?.[1];
      assert.ok(title, button);
      assert.equal(title, label);
    }
  }
});

test("lineage and topology zoom buttons use the corresponding accessible icons", () => {
  for (const topology of [false, true]) {
    const { context } = lineage({
      graphs: { feature_lineage: {}, feature_style: {}, invocation_lineage: {}, invocation_style: {} },
    }, topology);
    for (const [factor, name, label] of [["1.25", "zoom-in", "Zoom in"], ["0.8", "zoom-out", "Zoom out"]]) {
      const button = [...context.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)]
        .map(match => match[0]).find(markup => markup.includes(`data-zoom="${factor}"`));
      assert.ok(button);
      assert.ok(button.includes(`aria-label="${label}" title="${label}"`));
      assert.ok(button.includes(`data-lucide="${name}" aria-hidden="true"`));
      assert.doesNotMatch(button, />[+-]<\/button>/);
    }
  }
});

test("all lineage buttons share sizing and alignment with larger mobile touch targets", async () => {
  const styles = await readFile(new URL("../css/lineage.css", root), "utf8");
  const shared = styles.match(/\.lineage-control-groups \.ui-button \{([^}]+)\}/)[1];
  for (const rule of ["box-sizing: border-box", "display: inline-flex",
    "align-items: center", "justify-content: center", "flex-shrink: 0",
    "height: 40px", "min-width: 40px", "line-height: 1"]) {
    assert.ok(shared.includes(rule), rule);
  }
  assert.match(styles, /@media \(max-width: 640px\) \{\s*\.lineage-control-groups \.ui-button \{ height: 44px; min-width: 44px; \}/);
});

test("lineage groups have additional horizontal spacing without changing spacing within groups", async () => {
  const [lineage, base] = await Promise.all([
    readFile(new URL("../css/lineage.css", root), "utf8"),
    readFile(new URL("../css/base.css", root), "utf8"),
  ]);
  assert.match(lineage, /\.lineage-control-groups \{[^}]*gap: 8px 12px;/);
  assert.match(base, /\.mobile-primary-controls \.lineage-control-groups \{[^}]*gap: 6px 10px;/);
  assert.match(lineage, /\.lineage-buttons \{[^}]*gap: 4px;/);
});

test("stage argument bindings prefix names with type icons and preserve typed values", () => {
  const content = stageCards({ stages: [{ stage: 1, steps: [{
    title: "Binding", function_kind: "vectorize", function_label: "Calculate",
    feature: "score", returns: { type: { engine: "float" } },
    depends_on_invocations: [], row_context: null,
    args: { input: { value: "<unsafe>", type: {
      binding: "feature", function: "Series", engine: "float",
    } }, source: { value: "$params.source", type: {
      binding: null, function: "string", engine: null,
    } } },
  }] }] });
  assert.match(content, /<table class="ui-table">/);
  assert.match(content, /data-lucide="hash"[^>]*><\/i><span>input<\/span>/);
  assert.match(content, /<th scope="col">Argument<\/th><th scope="col">Value<\/th>/);
  assert.match(content, /&lt;unsafe&gt;/);
  assert.match(content, /data-type-label-text">float<\/span>/);
  assert.match(content, /data-lucide="case-sensitive"[^>]*><\/i><span>source<\/span>/);
  const table = content.match(/<table class="ui-table">[\s\S]*?<\/table>/)[0];
  assert.doesNotMatch(table, /Data type|Binding type|Function type|Engine type|data-type-label-text|>float<|>string</);
  assert.doesNotMatch(content, /data-type="Series"|data-type="feature"/);
  assert.doesNotMatch(content, /parallel invocation/);
});

test("Spec navigation no longer links to the removed overview", () => {
  const markup = shell({ project: {}, scope: {} }, "features", "", "");
  assert.doesNotMatch(markup, /href="\?view=spec"/);
  assert.match(markup, /aria-label="Profiles" title="Profiles" href="\?view=profiles"/);
});

test("main menu sections have noninteractive titles and separator styling", async () => {
  const markup = shell({ project: {}, scope: {} }, "plan", "", "");
  for (const [key, title] of [["spec", "Analytical model"], ["plan", "Execution plan"], ["execution", "Run results"]]) {
    assert.match(markup, new RegExp(`<section class="site-nav-group" aria-labelledby="nav-group-${key}">`));
    assert.match(markup, new RegExp(`<h2 class="site-nav-group-title" id="nav-group-${key}">${title}</h2>`));
    assert.doesNotMatch(markup, new RegExp(`<a[^>]*aria-label="${title}"`));
  }
  const styles = await readFile(new URL("../css/base.css", root), "utf8");
  assert.match(styles, /\.site-nav-group \+ \.site-nav-group \{ border-top: 1px solid #33415580/);
  assert.match(styles, /\.site-nav\.labels-hidden \.site-nav-group-title \{[\s\S]*?clip-path: inset\(50%\)/);
});

test("main menu preserves link order and marks only the current page active", () => {
  const markup = shell({ project: {}, scope: {} }, "preview", "", "");
  const groups = [...markup.matchAll(/<section class="site-nav-group"[^>]*>([\s\S]*?)<\/section>/g)];
  const routes = groups.map(([, content]) => [...content.matchAll(/href="\?view=([^"]+)"/g)]
    .map(([, route]) => route));
  assert.deepEqual(routes, [
    ["profiles", "features", "functions", "dimensions", "lineage"],
    ["plan", "topology", "stages"],
    ["info", "logs", "preview", "animation"],
  ]);
  assert.equal((markup.match(/aria-current="page"/g) || []).length, 1);
  assert.match(markup, /href="\?view=preview" aria-current="page"/);
});

test("icons and data type labels share neutral color and consistent typography", async () => {
  const [base, icons, spec] = await Promise.all([
    readFile(new URL("../css/base.css", root), "utf8"),
    readFile(new URL("../css/icons.css", root), "utf8"),
    readFile(new URL("../css/spec.css", root), "utf8"),
  ]);
  assert.match(base, /\.site-icon \{ color: inherit;/);
  assert.match(base, /\.context-links a\[aria-current="location"\] \{ color: var\(--color-selected\)/);
  assert.match(base, /\.site-subnav a\[aria-current="page"\] \{ color: var\(--color-selected\)/);
  assert.doesNotMatch(icons, /\.icon--/);
  assert.match(icons, /\.journey-step \{[\s\S]*?var\(--color-accent\)/);
  assert.match(icons, /\.data-lineage-node \{[\s\S]*?--icon-color:/);
  assert.match(base, /\.ui-badge--green/);
  assert.match(base, /\.data-type-label \{[^}]*font: 12px\/1\.5 var\(--font-mono\)/);
  assert.match(base, /\.data-type-label-icon \{[^}]*width: 14px/);
  assert.doesNotMatch(spec, /profile-schema-type-icon|dimension-resolution-type-icon/);
});

test("bookmarks for the removed spec overview redirect to Features", () => {
  let replacement;
  const browser = {
    location: { href: "https://example.test/?view=spec#old-section" },
    history: { replaceState(state, title, url) { replacement = url; } },
  };
  const router = new Router(browser, () => {});
  assert.equal(router.currentView(), "features");
  assert.equal(replacement.searchParams.get("view"), "features");
  assert.equal(replacement.hash, "");
  router.dispose();
});
