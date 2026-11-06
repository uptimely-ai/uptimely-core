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
const { badge, distribution, heading, icon, kindIcon, shell, statistic, contextHeader } = await import(shared);
const { dashboard, lineage, planOverview } = await import(pages);

test("Plan Stats uses the increasing bar chart icon in navigation and title", () => {
  const markup = shell({ project: {}, scope: {} }, "plan", "", "");
  assert.match(markup, /href="\?view=plan"[^>]*>[\s\S]*?data-lucide="chart-bar-increasing"[\s\S]*?Stats/);
  const content = planOverview({
    plan: { function_kind_counts: [], invocation_count: 0, stage_count: 0 },
    stages: [],
  });
  assert.match(content, /<h1[^>]*>[\s\S]*?data-lucide="chart-bar-increasing"[\s\S]*?<span>Stats<\/span><\/h1>/);
  assert.doesNotMatch(content, />Overview</);
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
  assert.match(content, />Produced schema<\/h3>/);
  assert.doesNotMatch(content, /Produced dataset/);
  const table = content.match(/<table data-dataset-schema="readings"[\s\S]*?<\/table>/)[0];
  assert.equal((table.match(/scope="col"/g) || []).length, 5);
  assert.match(table, />Producing action<\/th>/);
  assert.match(table, /None declared/);
  assert.equal((table.match(/scope="row"/g) || []).length, 2);
  assert.match(table, /data-schema-column="temperature"[\s\S]*?Temperature[\s\S]*?temperature[\s\S]*?Feature[\s\S]*?float[\s\S]*?>C<\/td>/);
  assert.match(table, /class="profile-schema-type"[\s\S]*?<span>float<\/span>/);
  assert.match(table, /<colgroup>/);
  assert.match(table, /data-schema-column="label"[\s\S]*?string[\s\S]*?—<\/td>/);
});

test("schema columns include every producing action including grain and vectorized features", () => {
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
  assert.deepEqual(columns.map(({ id, actions }) => [id, actions]), [
    ["machine_id", ["load"]], ["temperature", ["load"]],
    ["score", ["calculate", "revise"]], ["orphan", []],
  ]);
});

test("profile details show every declared action in order including vectorized actions", () => {
  const kinds = ["read", "vectorize", "expand", "vectorize", "collapse", "escape", "write"];
  const assembly = Object.fromEntries(kinds.map((kind, index) => [`action_${index}`, {
    compute: { function: kind, args: { output: `$outputs.value_${index}` } },
    interface: { inputs: [], outputs: [] },
  }]));
  const configuration = {
    dimensions: {},
    functions: Object.fromEntries(kinds.map(kind => [kind, { name: `${kind} function`, kind }])),
    profiles: { telemetry: { grain: [], features: {}, assembly } },
  };
  const render = () => renderCatalog({ catalogs: { summary: {}, configuration } }, "profiles").content;
  const content = render();
  assert.deepEqual([...content.matchAll(/data-profile-action="([^"]+)"/g)].map(match => match[1]),
    Object.keys(assembly));
  assert.equal((content.match(/data-action-kind="vectorize"/g) || []).length, 2);
  assert.match(content, /Argument bindings for action_1/);
  assert.match(content, /href="\?view=functions#function-vectorize">vectorize function/);
  assert.match(content, /\$outputs.value_1/);

  configuration.profiles.telemetry.assembly = { calculate: assembly.action_1 };
  const vectorizedOnly = render();
  assert.match(vectorizedOnly, />Actions<\/h3>/);
  assert.match(vectorizedOnly, /data-profile-action="calculate" data-action-kind="vectorize"/);
});

test("profile grain uses flat cards with dimension and resolution metadata", () => {
  const { content } = renderCatalog({ catalogs: { summary: {}, configuration: {
    functions: {}, dimensions: { machine: { name: "Machine", resolutions: {
      unit: { key: "machine_id", type: "string" },
    } } },
    profiles: { sample: { grain: [{ dimension: "machine", resolution: "unit" }],
      features: { machine_id: {} }, assembly: {} } },
  } } }, "profiles");
  const card = content.match(/<li class="profile-grain-card"[\s\S]*?<\/li>/)[0];
  assert.match(card, /<h4>Machine<\/h4>/);
  for (const [label, value] of [["Resolution", "unit"], ["Data key", "machine_id"], ["Data type", "string"]]) {
    assert.match(card, new RegExp(`<dt>${label}</dt><dd><code>${value}</code>`));
  }
  assert.doesNotMatch(card, /profile-grain-branch|<section|data-lucide/);
});

test("dimension details distinguish the dimension from its nested resolution levels", () => {
  const { content } = renderCatalog({
    catalogs: {
      summary: { dimension_count: 1 },
      configuration: { dimensions: {
        location: { name: "Location", resolutions: {
          country: { key: "country_id", type: "string" },
          city: { key: "city_id", type: "string", parent: "country" },
          site: { key: "site_id", type: "string", parent: "city" },
        } },
      } },
    },
  }, "dimensions");
  assert.match(content, /data-dimension-label[^>]*hidden>Dimension<\/p>/);
  assert.doesNotMatch(content, /<p[^>]*>location<\/p>/);
  assert.match(content, /aria-label="Resolution levels"/);
  assert.match(content, /Resolution levels, from parent to child\./);
  for (const id of ["country", "city", "site"]) {
    assert.match(content, new RegExp(`<h3 class="dimension-resolution-id">${id}</h3>`));
    assert.match(content, new RegExp(`data-lucide="case-sensitive"[\\s\\S]*?<code>${id}_id</code>`));
  }
  assert.match(content, /data-resolution-id="city" data-parent-resolution="country"/);
  assert.match(content, /data-resolution-id="site" data-parent-resolution="city"/);
  assert.equal((content.match(/class="dimension-resolution-children"/g) || []).length, 2);
  assert.doesNotMatch(content, /Parent resolution:|Top-level resolution|dimension-resolution-level|dimension-resolution-fields/);
});

test("Features stats contains the former spec feature role summary", () => {
  const data = {
    catalogs: {
      configuration: { profiles: {} },
      summary: {
        feature_buckets: { input: 3, intermediate: 2, output: 1 },
        feature_count: 6, vectorized_feature_count: 2,
      },
    },
  };
  const { content } = renderCatalog(data, "features");
  assert.match(content, /data-category="input" data-count="3"/);
  assert.match(content, /data-category="intermediate" data-count="2"/);
  assert.match(content, /data-category="output" data-count="1"/);
  assert.match(content, /total 6/);
  assert.match(content, /Vectorized features: 2/);
  assert.match(content, /<div class="catalog-charts">/);
});

test("all catalog summaries use shared Stats panels with the chart icon in navigation", () => {
  const data = {
    catalogs: {
      configuration: { profiles: {}, dimensions: {} },
      summary: { feature_buckets: {}, feature_count: 0 },
      function_groups: {},
    },
    plan: { function_kind_counts: [] },
    stages: [],
  };
  for (const view of ["profiles", "features", "functions", "dimensions", "stages"]) {
    const { content, context } = renderCatalog(data, view);
    const title = view[0].toUpperCase() + view.slice(1);
    assert.match(context, /href="#catalog-overview"[\s\S]*?data-lucide="chart-bar-increasing"[\s\S]*?>Stats</);
    assert.match(content, new RegExp(`aria-label="${title} stats"`));
    assert.match(content, new RegExp(`<h2 class="ui-section-title mb-6">${title} stats</h2>`));
    assert.match(content, /class="ui-panel" data-stat=/);
    assert.match(content, /class="ui-panel ui-chart"/);
    assert.doesNotMatch(content + context, />Overview<| overview</);
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
  assert.match(context, /id="reset-lineage"[^>]*>Reset topology</);
  assert.match(context, /id="invocation-node-details"/);
  assert.doesNotMatch(context, /Lineage context|Reset lineage/);
});

test("stage argument bindings use the shared table and preserve typed values", () => {
  const content = stageCards({ stages: [{ stage: 1, steps: [{
    title: "Binding", function_kind: "vectorize", function_label: "Calculate",
    feature: "score", returns: { type: { engine: "float" } },
    depends_on_invocations: [], row_context: null,
    args: { input: { value: "<unsafe>", type: {
      binding: "feature", function: "Series", engine: "float",
    } } },
  }] }] });
  assert.match(content, /<table class="ui-table">/);
  assert.match(content, /<th scope="row"><code>input<\/code>/);
  assert.match(content, /&lt;unsafe&gt;/);
  assert.match(content, /<code>Series<\/code>/);
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

test("icon colors are neutral by default with shared selection and semantic exceptions", async () => {
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
  assert.match(spec, /\.profile-schema-type-icon \{[^}]*color: inherit/);
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
