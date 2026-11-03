import { KINDS, contextHeader, contextLink, dataTypeIcon, display, distribution, escape, heading, href, icon, kindIcon, miniGraphic, page, statistic } from "../rendering/shared_markup.js";

export function profiles(configuration) {
  return Object.entries(configuration.profiles).map(([id, profile]) => ({
    id, profile, profileId: id,
  }));
}

const profileGrainKeys = (configuration, profile) => profile.grain.map(({ dimension, resolution }) =>
  configuration.dimensions[dimension]?.resolutions[resolution]?.key).filter(Boolean);

export function features(configuration) {
  return profiles(configuration).flatMap(item => {
    const produced = new Map();
    const grainKeys = new Set(profileGrainKeys(configuration, item.profile));
    for (const [actionId, action] of Object.entries(item.profile.actions)) {
      for (const reference of action.features.outputs) {
        const id = reference.replace(/^\$features\./, "");
        if (!grainKeys.has(id)) {
          produced.set(id, { ...item, featureId: id, feature: item.profile.features[id], actionId, action });
        }
      }
    }
    return [...produced.values()];
  });
}

const label = (id, value) => value.name || id;
const group = (title, items) => `<div class="context-link-group">
  <p class="context-group-label"><span>${escape(title)}</span><span class="context-link-count">${items.length}</span></p>${items.join("")}</div>`;
const description = value => `<p class="mt-4 text-sm leading-6 text-slate-400">${escape(value || "No description provided.")}</p>`;
const itemTitle = (id, item, tag = "h2", size = "text-2xl") => `<${tag} class="break-words font-display ${size} font-semibold text-white">${escape(label(id, item))}</${tag}>${item.name ? `<p class="mt-1 font-mono text-xs text-slate-500">${escape(id)}</p>` : ""}`;
const subheading = (title, lucideIcon = null) => `<h3 class="flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-[.16em] text-slate-300">${lucideIcon ? `<i data-lucide="${escape(lucideIcon)}" class="h-4 w-4 text-slate-400" aria-hidden="true"></i>` : ""}${escape(title)}</h3>`;
const chip = (value, isType = false) => `<span class="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">${isType ? dataTypeIcon(value, "h-3.5 w-3.5 opacity-70") : ""}${escape(value)}</span>`;
const chips = values => `<div class="mt-3 flex flex-wrap gap-2">${values.map(value =>
  chip(value)).join("")}</div>`;
const profileSchemaType = type => {
  const value = type || "unspecified";
  const typeIcon = dataTypeIcon(value, "profile-schema-type-icon");
  return typeIcon
    ? `${typeIcon}<span class="sr-only">${escape(value)}</span>`
    : escape(value);
};

const contextLinks = {
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    return profiles(config).map(({ id, profile }) => {
      const items = produced.filter(item => item.id === id);
      return items.length ? group(label(id, profile), items.map(item =>
        contextLink(`feature-${id}-${item.featureId}`, label(item.featureId, item.feature), "features"))) : "";
    }).join("");
  },
  profiles(data) {
    const categories = new Map();
    for (const [id, profile] of Object.entries(data.catalogs.configuration.profiles)) {
      const category = profile.category || "Uncategorized";
      if (!categories.has(category)) categories.set(category, []);
      categories.get(category).push(contextLink(`profile-${id}`, label(id, profile), "profiles"));
    }
    return [...categories].map(([category, links]) => group(category, links)).join("");
  },
  functions(data) {
    return Object.entries(data.catalogs.function_groups).filter(([, items]) => Object.keys(items).length)
      .map(([kind, items]) => `<div class="context-link-group">
        ${contextLink(`functions-${kind}`, kind[0].toUpperCase() + kind.slice(1), null, Object.keys(items).length, kind)}
        <div class="context-sublinks">${Object.entries(items).map(([id, item]) =>
          contextLink(`function-${id}`, label(id, item))).join("")}</div></div>`).join("");
  },
  stages(data) {
    return data.stages.map(stage =>
      contextLink(`stage-${stage.stage}`, `Stage ${stage.stage}`, "stages", stage.steps.length)).join("");
  },
  dimensions(data) {
    return Object.entries(data.catalogs.configuration.dimensions).map(([key, item]) => {
      const id = item.id ?? key;
      return contextLink(`dimension-${id}`, label(id, item), "dimensions");
    }).join("");
  },
};

export function catalogContext(data, view) {
  const links = contextLinks[view](data);
  const title = view[0].toUpperCase() + view.slice(1);
  return `<aside class="site-context" id="catalog-context" aria-label="${title} context" data-context-label="${view}">
    ${contextHeader(title, view, "catalog-context")}
    <button class="ui-button context-close" type="button" aria-label="Close ${view} context">Close</button>
    <nav class="context-links" aria-label="${title} on this page">${contextLink("catalog-overview", "Overview", "overview")}
      <hr class="context-separator">${links || `<p class="context-empty">No ${view}.</p>`}
    </nav></aside>`;
}

const overviewData = {
  profiles(data) {
    const { configuration: config, summary } = data.catalogs;
    const categoryCounts = new Map();
    Object.values(config.profiles).forEach(profile => {
      const category = profile.category || "Uncategorized";
      categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);
    });
    return {
      stats: [["Profiles", summary.profile_count], ["Categories", categoryCounts.size],
        ["Features", profiles(config).reduce((total, { profile }) => total + Object.keys(profile.features).length, 0)],
        ["Actions", summary.action_count, "invocations"]],
      charts: [distribution("Profiles by category", [...categoryCounts])],
    };
  },
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    return {
      stats: [["Features", produced.length],
        ["Profiles with features", new Set(produced.map(item => item.id)).size, "profiles"]],
      charts: [distribution("Features by profile", profiles(config).map(({ id }) =>
        [id, produced.filter(item => item.id === id).length]))],
    };
  },
  dimensions(data) {
    const { configuration: config, summary } = data.catalogs;
    const dimensions = Object.values(config.dimensions);
    const resolutions = dimensions.flatMap(item => Object.values(item.resolutions));
    const types = new Map();
    resolutions.forEach(item => types.set(item.type, (types.get(item.type) || 0) + 1));
    const roots = resolutions.filter(item => !item.parent).length;
    return {
      stats: [["Dimensions", summary.dimension_count], ["Resolutions", resolutions.length],
        ["Types", types.size, "resolutions"], ["Root resolutions", roots, "resolutions"],
        ["Child resolutions", resolutions.length - roots, "resolutions"]],
      charts: [distribution("Resolutions by type", [...types])],
    };
  },
  stages(data) {
    return {
      stats: [["Stages", data.plan.stage_count], ["Invocations", data.plan.invocation_count],
        ["Max parallel invocations", data.plan.max_parallel_invocations, "stages"],
        ["Dependencies", data.plan.dependency_count, "invocation-lineage"]],
      charts: [
        distribution("Invocations by stage",
          data.stages.map(stage => [`Stage ${stage.stage}`, stage.steps.length])),
        distribution("Invocations by function kind", data.plan.function_kind_counts),
      ],
    };
  },
};

function catalogOverview(data, view) {
  if (view === "functions") return functionOverview(data);
  const { stats, charts } = overviewData[view](data);
  const title = view[0].toUpperCase() + view.slice(1);
  return `<section id="catalog-overview" data-context-item aria-label="${title} overview" class="mb-12">
    <h2 class="title-with-icon mb-6 font-display text-2xl font-semibold text-white">${icon("overview")}<span>${title} overview</span></h2>
    <div class="grid gap-3 sm:grid-cols-2${stats.length > 2 ? " lg:grid-cols-4" : ""}">${stats.map(args => statistic(...args)).join("")}</div>${charts.join("")}
  </section>`;
}

function functionOverview(data) {
  const groups = Object.entries(data.catalogs.function_groups);
  const maximum = Math.max(0, ...groups.map(([, items]) => Object.keys(items).length));
  return `<section id="catalog-overview" data-context-item aria-label="Functions overview" class="mb-14 rounded-2xl border border-slate-800 bg-slate-900/75 p-5 sm:p-6">
    <h2 class="title-with-icon mb-6 font-display text-2xl font-semibold text-white">${icon("overview")}<span>Functions overview</span></h2>
    <div class="mb-6 grid gap-3 sm:grid-cols-2">${[
      ["Functions", data.catalogs.summary.function_count],
      ["Kinds in use", groups.filter(([, items]) => Object.keys(items).length).length],
    ].map(([title, value]) => `<div class="rounded-xl border border-slate-800 bg-slate-950/55 p-5" data-stat="${title}">
      <div class="flex items-center justify-between gap-3"><span class="text-xs text-slate-400">${title}</span>${icon("functions")}</div>
      <p class="mt-4 font-display text-3xl font-semibold text-white" data-value="${value}">${value}</p></div>`).join("")}</div>
    <div class="mb-5 flex items-baseline justify-between gap-4"><h2 class="font-display text-lg font-semibold text-white">Functions by kind</h2>
      <span class="font-mono text-[10px] uppercase tracking-wider text-slate-500">total ${data.catalogs.summary.function_count}</span></div>
    <div class="space-y-1.5">${groups.map(([kind, items]) => {
      const count = Object.keys(items).length, tag = count ? "a" : "div";
      return `<${tag}${count ? ` href="#functions-${encodeURIComponent(kind)}"` : ""} data-category="${escape(kind)}" data-count="${count}"
        class="${count ? "group rounded-lg transition hover:bg-slate-800/50" : "opacity-45"} grid grid-cols-[7.5rem_minmax(0,1fr)_2.5rem] items-center gap-3 px-2 py-2">
        <span class="flex items-center gap-2 font-mono text-xs ${count ? "text-slate-400 transition group-hover:text-slate-200" : "text-slate-500"}">
          <i data-lucide="${KINDS[kind]?.icon || "braces"}" class="h-3.5 w-3.5 ${kind === "escape" ? "text-violet-300" : "text-cyan-300"}" aria-hidden="true"></i>${escape(kind)}</span>
        <span class="h-2 overflow-hidden rounded-full bg-slate-800"><span class="block h-full rounded-full ${kind === "escape" ? "bg-violet-400" : "bg-cyan-400"}" style="width:${maximum ? count / maximum * 100 : 0}%"></span></span>
        <span class="text-right font-mono text-xs ${count ? "text-white" : "text-slate-500"}">${count}</span></${tag}>`;
    }).join("")}</div></section>`;
}

function featureCards(config) {
  return features(config).map(item => {
    const fn = config.functions[item.action.binding.function] || {};
    return `<article id="feature-${escape(item.id)}-${escape(item.featureId)}" data-context-item>
      ${itemTitle(item.featureId, item.feature)}
      <p data-feature-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.feature.description || "No description provided.")}</p>
      <section class="mt-6 rounded-xl border border-cyan-900/60 bg-cyan-950/20 p-4 sm:p-5">
        <h3 class="flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-[.14em] text-cyan-200">${icon("functions", "h-4 w-4")}Produced by ${escape(fn.name || item.action.binding.function)}</h3>
        <p class="mt-3 flex items-center gap-2 text-xs text-slate-400">${kindIcon(fn.kind, "h-3.5 w-3.5")}<span class="font-mono text-cyan-100">${escape(fn.kind || "Unspecified")}</span></p>
        ${description(fn.description)}
      </section>
      <dl class="mt-6 grid gap-6 sm:grid-cols-2">${[
        ["Profile", label(item.id, item.profile), "profiles", href("profiles", `profile-${item.id}`)],
        ["Type", item.feature.type || "unspecified", "features"],
        ["Unit", item.feature.unit || "Not specified", "dimensions"],
      ].map(([title, value, key, url]) => `<div><dt class="flex items-center gap-2 text-xs text-slate-500">${icon(key, "h-3.5 w-3.5")}${title}</dt>
        <dd class="mt-2 break-words font-mono text-sm text-slate-300">${url ? `<a href="${url}">${escape(value)}</a>` : escape(value)}</dd></div>`).join("")}</dl>
      ${fn.kind === "escape" ? '<p class="mt-6 text-sm leading-6 text-violet-300">Declared logical output only; escape outputs are not materialized as dataframe columns.</p>' : ""}
    </article>`;
  }).join("");
}

function resolutionHierarchy(resolutions) {
  const nodes = Object.entries(resolutions).map(([key, resolution]) => ({
    id: resolution.id ?? key,
    resolution,
    children: [],
  }));
  const nodesById = new Map(nodes.map(node => [node.id, node]));
  const roots = [];
  for (const node of nodes) {
    const parent = nodesById.get(node.resolution.parent);
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  }

  const rendered = new Set();
  const renderNode = node => {
    if (rendered.has(node)) return "";
    rendered.add(node);
    const { resolution } = node;
    return `<li data-resolution-id="${escape(node.id)}" data-parent-resolution="${escape(resolution.parent || "")}">
      <article class="dimension-resolution-card">
        <header class="dimension-resolution-heading">
          <span class="dimension-resolution-symbol"><i data-lucide="layers-3" aria-hidden="true"></i></span>
          <div class="min-w-0">
            <span class="dimension-resolution-label">Resolution ID</span>
            <h3 class="dimension-resolution-id">${escape(node.id)}</h3>
          </div>
          <span class="dimension-resolution-level">${resolution.parent ? `Parent · ${escape(resolution.parent)}` : "Top level"}</span>
        </header>
        <dl class="dimension-resolution-fields">
          <div class="dimension-resolution-field">
            <dt><i data-lucide="key-round" aria-hidden="true"></i>Data key</dt>
            <dd><code>${escape(resolution.key)}</code></dd>
          </div>
          <div class="dimension-resolution-field">
            <dt><i data-lucide="braces" aria-hidden="true"></i>Data type</dt>
            <dd>${dataTypeIcon(resolution.type, "dimension-resolution-type-icon")}<code>${escape(resolution.type)}</code></dd>
          </div>
        </dl>
      </article>
      ${node.children.length ? `<ul class="dimension-resolution-children">${node.children.map(renderNode).join("")}</ul>` : ""}
    </li>`;
  };
  return `<ul aria-label="Resolution hierarchy" class="dimension-resolution-tree">${[...roots, ...nodes].map(renderNode).join("")}</ul>`;
}

function dimensionCards(config) {
  return Object.entries(config.dimensions).map(([key, item]) => {
    const id = item.id ?? key;
    return `<article id="dimension-${escape(id)}" data-context-item class="min-w-0">
    ${itemTitle(id, item, "h2", "text-lg")}
    <div class="mt-3">${resolutionHierarchy(item.resolutions)}</div>
    <p data-dimension-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.description || "No description provided.")}</p></article>`;
  }).join("");
}

export function schemaColumns(config, profile) {
  const grainKeys = new Set(profileGrainKeys(config, profile));
  const producers = new Map();
  for (const action of Object.values(profile.actions)) {
    const kind = config.functions[action.binding.function]?.kind;
    for (const ref of action.features.outputs) {
      const id = ref.replace(/^\$features\./, "");
      if (!producers.has(id)) producers.set(id, kind === "escape" ? "escape" : ["vectorize", "collapse"].includes(kind) ? "amber" : "teal");
    }
  }
  return [
    ...[...grainKeys].map(id => ({ id, ...profile.features[id], role: "Dimension", color: "dimension" })),
    ...Object.entries(profile.features).filter(([id]) => !grainKeys.has(id)).map(([id, feature]) => {
      const color = producers.get(id) || "neutral";
      return { id, ...feature, color, role: color === "teal" ? "Raw" : color === "escape" ? "External" : "Feature" };
    }),
  ];
}

function grainCards(config, grain) {
  return grain.map(({ dimension, resolution }) => {
    const dimensionDefinition = config.dimensions[dimension];
    const resolutionDefinition = dimensionDefinition?.resolutions[resolution];
    const resolutionId = resolutionDefinition?.id ?? resolution;
    return `<li class="profile-grain-card" data-grain-dimension="${escape(dimension)}" data-grain-resolution="${escape(resolutionId)}">
      <header class="profile-grain-heading">
        <span class="profile-grain-icon"><i data-lucide="axis-3d" aria-hidden="true"></i></span>
        <div class="min-w-0">
          <span class="profile-grain-label">Dimension</span>
          <h4>${escape(dimensionDefinition?.name || dimension)}</h4>
        </div>
      </header>
      <div class="profile-grain-branch">
        <section class="profile-grain-resolution" aria-label="Selected resolution">
          <header><span class="profile-grain-label">Resolution</span><h5><code>${escape(resolutionId)}</code></h5></header>
          <dl class="profile-grain-fields">
            <div><dt>Data key</dt><dd><code>${escape(resolutionDefinition?.key || resolution)}</code></dd></div>
            <div><dt>Data type</dt><dd>${dataTypeIcon(resolutionDefinition?.type, "profile-grain-type-icon")}<code>${escape(resolutionDefinition?.type || "unspecified")}</code></dd></div>
          </dl>
        </section>
      </div>
    </li>`;
  }).join("");
}

function profileActionCards(config, profile, actions) {
  const featureList = references => references.length
    ? references.map(reference => `<code>${escape(reference.replace(/^\$features\./, ""))}</code>`).join("")
    : '<span class="profile-action-empty">None declared</span>';
  return `<div class="profile-actions">${actions.map(([id, action]) => {
    const functionId = action.binding.function;
    const fn = config.functions[functionId] || {};
    const args = Object.entries(action.binding.args || {});
    return `<article class="profile-action" data-profile-action="${escape(id)}" data-action-kind="${escape(fn.kind)}">
      <header class="profile-action-header">
        <span class="profile-action-symbol">${kindIcon(fn.kind, "profile-action-icon")}</span>
        <div class="profile-action-identity"><span class="profile-action-label">Action ID</span><h4>${escape(id)}</h4></div>
        <span class="profile-action-kind">${escape(fn.kind || "Unspecified")}</span>
      </header>
      ${args.length ? `<details class="profile-action-bindings"><summary>Argument bindings <span>${args.length}</span></summary>
        <div class="profile-action-table-scroll"><table><caption class="sr-only">Argument bindings for ${escape(id)}</caption>
          <thead><tr><th scope="col">Argument</th><th scope="col">Binding</th></tr></thead>
          <tbody>${args.map(([name, value]) => `<tr><th scope="row">${escape(name)}</th><td><code>${display(value)}</code></td></tr>`).join("")}</tbody>
        </table></div></details>` : ""}
      <div class="profile-action-function"><span class="profile-action-label">Function</span>
        <a href="${href("functions", `function-${functionId}`)}">${escape(fn.name || functionId)}</a>
        ${fn.name && fn.name !== functionId ? `<code>${escape(functionId)}</code>` : ""}
      </div>
      <dl class="profile-action-contract">
        <div><dt>Input features</dt><dd>${featureList(action.features.inputs)}</dd></div>
        <div><dt>Output features${fn.kind === "escape" ? " (logical)" : ""}</dt><dd>${featureList(action.features.outputs)}</dd></div>
      </dl>
      ${fn.kind === "collapse" ? `<div class="profile-action-note">Input profile inferred from bound features · Group by grain keys: <code>${display(profileGrainKeys(config, profile))}</code></div>` : ""}
      ${fn.kind === "escape" ? '<div class="profile-action-note">External effects are uncontrolled. Declared inputs and outputs express logical dependencies only; escape outputs are not materialized as dataframe columns.</div>' : ""}
    </article>`;
  }).join("")}</div>`;
}

function profileCards(config) {
  const colors = {
    dimension: "bg-[#172b46] text-[#b5d4f8]", teal: "bg-[#15352e] text-[#a5dfca]",
    escape: "bg-[#30234a] text-[#d8b4fe]", amber: "bg-[#392e19] text-[#efcf89]",
    neutral: "bg-slate-800 text-slate-300",
  };
  return profiles(config).map(({ id, profile }) => {
    const columns = schemaColumns(config, profile);
    const grain = profile.grain;
    const actions = Object.entries(profile.actions).filter(([, action]) => config.functions[action.binding.function]?.kind !== "vectorize");
    return `<article id="profile-${escape(id)}" data-context-item>
      <div hidden>
        <h2>${escape(label(id, profile))}</h2>
        ${profile.description ? `<p data-profile-description>${escape(profile.description)}</p>` : ""}
      </div>
      <section aria-label="Profile details">
        <div class="space-y-6">
          ${grain.length ? `<div>${subheading("Grain", "axis-3d")}<ul class="profile-grain-grid">${grainCards(config, grain)}</ul></div>` : ""}
          ${profile.scope || profile.order?.length ? `<div class="grid gap-6 ${profile.scope && profile.order?.length ? "md:grid-cols-2" : ""}" data-profile-context>
          ${profile.scope ? `<div class="min-w-0">${subheading("Scope", "scan")}${description(profile.scope)}</div>` : ""}
          ${profile.order?.length ? `<div class="min-w-0">${subheading("Logical order", "list-ordered")}<p class="mt-2 text-xs text-slate-500">Not a physical row-order guarantee.</p>${chips(profile.order.map(key => {
            const dimensionId = key.dimension;
            const dimension = config.dimensions[dimensionId];
            const resolution = dimension?.resolutions[key.resolution];
            return `${dimension?.name || dimensionId} · ${resolution?.key || key.resolution} ${key.direction}`;
          }))}</div>` : ""}</div>` : ""}
          <div>${subheading("Produced dataset", "table-2")}<div class="dataset-table-scroll mt-3 overflow-x-auto rounded-xl border border-slate-700/60">
        <table data-dataset-schema="${escape(id)}" class="w-full min-w-max border-collapse text-left font-mono text-xs">
          <caption class="sr-only">Declared column types and units for ${escape(label(id, profile))}; schema only, no sample records.</caption>
          <thead><tr>${columns.map(column => `<th scope="col" class="border-b border-slate-700/50 px-4 py-4 ${colors[column.color]}">${escape(label(column.id, column))}
            <span class="mt-2 block text-[10px] font-normal">${column.role}</span><span class="mt-1 block text-[9px] font-normal text-slate-500">${escape(column.id)}</span></th>`).join("")}</tr></thead>
          <tbody><tr>${columns.map(column => `<td class="border-b border-slate-800/60 px-4 py-3 text-lime-300"><span class="inline-flex items-center gap-1.5">${profileSchemaType(column.type)}</span></td>`).join("")}</tr>
            <tr>${columns.map(column => `<td class="px-4 py-3 text-slate-400">${escape(column.unit || "—")}</td>`).join("")}</tr></tbody>
        </table></div></div>
          ${actions.length ? `<div>${subheading("Actions", "square-function")}${profileActionCards(config, profile, actions)}</div>` : ""}
        </div></section></article>`;
  }).join("");
}

function functionCards(data) {
  return Object.entries(data.catalogs.function_groups).filter(([, items]) => Object.keys(items).length).map(([kind, items]) =>
    `<div id="functions-${escape(kind)}" data-function-group="${escape(kind)}" class="mb-20 scroll-mt-24"><div class="space-y-10">
      ${Object.entries(items).map(([id, fn]) => `<article id="function-${escape(id)}" data-context-item>
        ${itemTitle(id, fn, "h3")}
        <p data-function-description class="mt-4 max-w-3xl text-base leading-7 text-slate-300">${escape(fn.description || "No description provided.")}</p>
        ${fn.doc?.body ? `<p class="mt-3 max-w-3xl whitespace-pre-line text-sm leading-7 text-slate-400">${escape(fn.doc.body)}</p>` : ""}
        <div class="mt-10 grid gap-6 ${fn.doc?.examples?.length ? "lg:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]" : "max-w-xl"}">
          ${fn.doc?.examples?.length ? `<section class="min-w-0">${subheading("Example")}
            <pre class="mt-3 min-h-40 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-5 font-mono text-xs leading-6 text-slate-300"><code class="language-python">${escape(fn.doc.examples[0])}</code></pre></section>` : ""}
          <section class="min-w-0">${subheading("Demonstration")}<div class="mt-3 flex min-h-40 items-center justify-center overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-5">${miniGraphic(kind)}</div></section></div>
        ${(fn.doc?.examples || []).slice(1).map((example, index) => `<section class="mt-6">${subheading(`Example ${index + 2}`)}<pre class="mt-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-5 font-mono text-xs leading-6 text-slate-300"><code class="language-python">${escape(example)}</code></pre></section>`).join("")}
        ${fn.kind === "escape" ? `<p class="mt-10 text-sm leading-6 text-violet-200/90">Uncontrolled external operation: declared feature inputs and outputs express logical dependencies only. Dataframes are passed only through explicitly bound arguments, and the return value is ignored.</p>
          ${fn.escape_actions?.length ? `<div class="mt-10">${subheading("Used by actions")}${fn.escape_actions.map(action => `<div class="py-4">
            <p class="font-mono text-xs text-slate-200">${escape(action.profile)} · ${escape(action.action)}</p>
            <p class="mt-2 font-mono text-xs text-slate-400">Declared inputs: ${escape(action.inputs.join(", ") || "none")}</p>
            <p class="mt-1 font-mono text-xs text-slate-400">Declared outputs: ${escape(action.outputs.join(", ") || "none")}</p></div>`).join("")}</div>` : ""}` : ""}
        ${Object.keys(fn.args || {}).length ? `<div class="mt-10">${subheading("Arguments")}<dl class="mt-3 divide-y divide-slate-800/60">${Object.entries(fn.args).map(([key, arg]) => `<div class="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <dt class="flex flex-wrap items-start gap-2"><span class="font-mono text-sm font-medium text-cyan-200">${escape(key)}</span><span class="rounded-md border border-lime-400/20 bg-lime-400/5 px-2 py-0.5 font-mono text-[11px] text-lime-300">${escape(arg.type || "unspecified")}</span></dt>
          <dd class="text-sm leading-6 text-slate-400">${escape(fn.doc?.params?.[key] || arg.comment || "—")}</dd></div>`).join("")}</dl></div>` : ""}
        ${fn.doc?.returns || fn.return_type ? `<div class="mt-10">${subheading("Returns")}${fn.return_type ? `<p class="mt-3 font-mono text-xs text-lime-300">-&gt; ${escape(fn.return_type)}</p>` : ""}${fn.doc?.returns ? description(fn.doc.returns) : ""}</div>` : ""}
        ${fn.doc?.raises?.length ? `<div class="mt-10">${subheading("Raises")}<ul class="mt-3 space-y-2">${fn.doc.raises.map(error => `<li class="text-sm leading-6 text-slate-400"><span class="font-mono text-amber-300">${escape(error.type)}</span> — ${escape(error.description)}</li>`).join("")}</ul></div>` : ""}
        ${fn.entrypoint || fn.signature_validation_disabled ? `<div class="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-slate-800/60 pt-5">
          <span class="break-all font-mono text-xs text-slate-400">${escape(fn.entrypoint)}</span>${fn.signature_validation_disabled ? '<span class="rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 font-mono text-[10px] text-amber-200">Python signature validation disabled</span>' : ""}</div>` : ""}
      </article>`).join("")}</div></div>`).join("");
}

export function stageCards(data) {
  return data.stages.map(stage => `<section id="stage-${stage.stage}" data-context-item>
    <div class="mb-3 flex items-center gap-3"><h2 class="rounded-lg bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">Stage ${stage.stage}</h2>
      <span class="font-mono text-[10px] uppercase tracking-wider text-slate-500">${stage.steps.length} parallel invocation${stage.steps.length === 1 ? "" : "s"}</span></div>
    <div class="grid grid-cols-1 gap-10">${stage.steps.map(step => `<div>
      <h3 class="mb-2 break-words font-display text-lg font-semibold text-white">${escape(step.title)}</h3><article>
        <dl class="grid overflow-hidden rounded-lg border border-slate-800 bg-slate-950/55 font-mono text-xs md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_10rem]">
          ${[["Function kind", step.function_kind, "text-amber-200"], ["Function", step.function_label, "text-white"],
            [step.uncontrolled ? "Declared logical outputs" : "Profile feature output", step.feature || "None", "text-cyan-200"],
            [step.uncontrolled ? "Python return (ignored)" : "Returns", step.returns.type.engine || "—", "text-lime-300"]].map(([title, value, color]) => `<div class="min-w-0 border-b border-slate-800 p-3 md:border-r">
              <dt class="mb-1 uppercase tracking-wider text-slate-500">${title}</dt><dd class="break-all ${color}">${escape(value)}</dd></div>`).join("")}
          <div class="min-w-0 p-3 md:col-span-4"><dt class="mb-1 uppercase tracking-wider text-slate-500">Depends on invocations</dt>
            <dd class="flex flex-wrap gap-1.5">${step.depends_on_invocations.map(dep => `<span class="rounded-md bg-slate-950/70 px-2 py-1 text-slate-300">${escape(dep.function)}</span>`).join("") || '<span class="text-slate-400">No invocation dependencies</span>'}</dd></div>
        </dl>
        ${step.dataset_label ? `<p class="mt-3 font-mono text-xs text-slate-500">Profile: ${escape(step.dataset_label)}</p>` : ""}
        ${step.uncontrolled ? `<p class="mt-3 rounded-lg border border-violet-900/60 bg-violet-950/30 p-3 text-xs leading-5 text-violet-200">Uncontrolled external operation. Declared inputs: ${escape(step.input_features.join(", ") || "none")}. Declared outputs: ${escape(step.output_features.join(", ") || "none")}. These are logical dependencies only; dataframes are passed only through explicit arguments, and escape return values are ignored.</p>` : ""}
        ${step.row_context !== null ? `<div class="mt-3 font-mono text-xs text-slate-400">Row context: ${display(step.row_context)}</div>` : ""}
        ${Object.keys(step.args).length ? `<div class="mt-5 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80"><table class="w-full font-mono text-xs">
          <thead><tr class="border-b border-slate-800 text-left text-slate-500">${["Argument", "Value", "Binding type", "Function type", "Engine type"].map(title => `<th class="px-4 py-2 font-normal uppercase tracking-wider">${title}</th>`).join("")}</tr></thead>
          <tbody>${Object.entries(step.args).map(([id, arg]) => `<tr class="border-b border-slate-800/60 last:border-0"><td class="px-4 py-2 text-cyan-200">${escape(id)}</td>
            <td class="break-all px-4 py-2 text-white">${display(arg.value)}</td>${["binding", "function", "engine"].map(key => `<td class="px-4 py-2 ${key === "engine" ? "text-lime-300" : "text-slate-400"}">${escape(arg.type[key] || "—")}</td>`).join("")}</tr>`).join("")}</tbody>
          </table></div>` : ""}</article></div>`).join("")}</div></section>`).join("");
}

export function renderCatalog(data, view) {
  const config = data.catalogs.configuration;
  const renderers = { features: () => featureCards(config), profiles: () => profileCards(config),
    dimensions: () => dimensionCards(config),
    functions: () => functionCards(data), stages: () => stageCards(data) };
  const title = view[0].toUpperCase() + view.slice(1);
  const descriptions = {
    functions: "Browse the function catalog, argument types, return signatures, and source entrypoints.",
    dimensions: "Inspect dimension resolutions, dataframe keys, and their parent relationships.",
    features: "",
    profiles: "",
  };
  return {
    context: catalogContext(data, view),
    content: `<button class="ui-button context-toggle catalog-context-toggle" type="button" aria-label="Show ${view} context"
      aria-expanded="false" aria-controls="catalog-context">Browse ${view}</button>` + page(`<section id="${view}" class="mb-16">
      ${view === "stages" ? '<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Plan</p>' : ""}
      ${heading(title, descriptions[view] ?? null, view, view === "features" ? features(config).length : null)}
      ${catalogOverview(data, view)}<div class="space-y-8">${renderers[view]()}</div></section>`),
  };
}
