import { badge, contextGroup as group, contextHeader, contextLink, dataTypeLabel, display, distribution, escape, heading, href, icon, kindIcon, miniGraphic, page, statistic, typedName } from "../rendering/shared_markup.js";

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
    for (const [operatorId, operator] of Object.entries(item.profile.assembly)) {
      for (const reference of operator.interface.outputs) {
        const id = reference.replace(/^\$features\./, "");
        if (!grainKeys.has(id)) {
          produced.set(id, { ...item, featureId: id, feature: item.profile.features[id], operatorId, operator });
        }
      }
    }
    return [...produced.values()];
  });
}

const label = (id, value) => value.name || id;
const description = value => `<p class="mt-4 text-sm leading-6 text-slate-400">${escape(value || "No description provided.")}</p>`;
const itemTitle = (id, item, tag = "h2", size = "text-2xl", type = null) => `<${tag} class="break-words font-display ${size} font-semibold text-white">${type === null ? escape(label(id, item)) : typedName(label(id, item), type)}</${tag}>${item.name ? `<p class="mt-1 font-mono text-xs text-slate-500">${escape(id)}</p>` : ""}`;
const subheading = title => `<h3 class="ui-section-title">${escape(title)}</h3>`;
const chip = (value, isType = false) => isType
  ? dataTypeLabel(value, "rounded-md bg-slate-800 px-2.5 py-1 text-slate-300")
  : `<span class="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">${escape(value)}</span>`;
const chips = values => `<div class="mt-3 flex flex-wrap gap-2">${values.map(value =>
  chip(value)).join("")}</div>`;

const contextLinks = {
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    return profiles(config).map(({ id, profile }) => {
      const items = produced.filter(item => item.id === id);
      return items.length ? group(label(id, profile), items.map(item =>
        contextLink(`feature-${id}-${item.featureId}`, label(item.featureId, item.feature), null,
          null, null, item.feature.type || "unspecified"))) : "";
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
      .map(([kind, items]) => group(kind[0].toUpperCase() + kind.slice(1),
        Object.entries(items).map(([id, item]) =>
          contextLink(`function-${id}`, label(id, item), "functions")))).join("");
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
    <nav class="context-links" aria-label="${title} on this page">${contextLink("catalog-overview", "Stats", "stats")}
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
        ["Operator", summary.operator_count]],
      charts: [distribution("Profiles by category", [...categoryCounts])],
    };
  },
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    const summary = data.catalogs.summary;
    return {
      stats: [["Features", produced.length],
        ["Profiles with features", new Set(produced.map(item => item.id)).size]],
      charts: [distribution("Features by role",
        ["input", "intermediate", "output"].map(key => [key, summary.feature_buckets[key] || 0]),
        { total: summary.feature_count, note: `Vectorized features: ${summary.vectorized_feature_count ?? 0}` }),
        distribution("Features by profile", profiles(config).map(({ id, profile }) =>
        [label(id, profile), produced.filter(item => item.id === id).length]))],
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
        ["Types", types.size], ["Root resolutions", roots],
        ["Child resolutions", resolutions.length - roots]],
      charts: [distribution("Resolutions by type", [...types], { typeLabels: true })],
    };
  },
  stages(data) {
    return {
      stats: [["Stages", data.plan.stage_count], ["Invocations", data.plan.invocation_count],
        ["Max parallel invocations", data.plan.max_parallel_invocations],
        ["Dependencies", data.plan.dependency_count]],
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
  return `<section id="catalog-overview" data-context-item aria-label="${title} stats" class="mb-12">
    <h2 class="ui-section-title mb-6">${title} stats</h2>
    <div class="grid gap-3 sm:grid-cols-2${stats.length > 2 ? " lg:grid-cols-4" : ""}">${stats.map(args => statistic(...args)).join("")}</div>
    <div class="catalog-charts">${charts.join("")}</div>
  </section>`;
}

function functionOverview(data) {
  const groups = Object.entries(data.catalogs.function_groups);
  return `<section id="catalog-overview" data-context-item aria-label="Functions stats" class="mb-12">
    <h2 class="ui-section-title mb-6">Functions stats</h2>
    <div class="grid gap-3 sm:grid-cols-2">${[
      ["Functions", data.catalogs.summary.function_count],
      ["Kinds in use", groups.filter(([, items]) => Object.keys(items).length).length],
    ].map(args => statistic(...args)).join("")}</div>
    <div class="catalog-charts">${distribution("Functions by kind", groups.map(([kind, items]) => {
      const count = Object.keys(items).length;
      return [kind, count, count ? `#functions-${encodeURIComponent(kind)}` : null];
    }), { total: data.catalogs.summary.function_count })}</div></section>`;
}

function featureCards(config) {
  return features(config).map(item => {
    const fn = config.functions[item.operator.compute.function] || {};
    return `<article id="feature-${escape(item.id)}-${escape(item.featureId)}" data-context-item>
      ${itemTitle(item.featureId, item.feature, "h2", "text-2xl", item.feature.type || "unspecified")}
      <p data-feature-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.feature.description || "No description provided.")}</p>
      <section class="mt-6 rounded-xl border border-cyan-900/60 bg-cyan-950/20 p-4 sm:p-5">
        <h3 class="ui-section-title">Producing function: ${escape(fn.name || item.operator.compute.function)}</h3>
        <p class="mt-3 flex items-center gap-2 text-xs text-slate-400">${kindIcon(fn.kind, "h-3.5 w-3.5")}<span class="font-mono text-cyan-100">${escape(fn.kind || "Unspecified")}</span></p>
        ${description(fn.description)}
      </section>
      <dl class="mt-6 grid gap-6 sm:grid-cols-2">${[
        ["Profile", label(item.id, item.profile), href("profiles", `profile-${item.id}`)],
        ["Unit", item.feature.unit || "Not specified"],
      ].map(([title, value, url]) => `<div><dt class="text-xs text-slate-500">${title}</dt>
        <dd class="mt-2 break-words text-slate-300">${url ? `<a href="${url}">${escape(value)}</a>` : escape(value)}</dd></div>`).join("")}</dl>
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
    const type = resolution.type || "unspecified";
    return `<li data-resolution-id="${escape(node.id)}" data-parent-resolution="${escape(resolution.parent || "")}">
      <article class="dimension-resolution-card">
        <h3 class="dimension-resolution-id">${typedName(node.id, type)}</h3>
      </article>
      ${node.children.length ? `<ul class="dimension-resolution-children">${node.children.map(renderNode).join("")}</ul>` : ""}
    </li>`;
  };
  return `<ul aria-label="Resolution hierarchy" class="dimension-resolution-tree">${[...roots, ...nodes].map(node => renderNode(node)).join("")}</ul>`;
}

function dimensionCards(config) {
  return Object.entries(config.dimensions).map(([key, item]) => {
    const id = item.id ?? key;
    return `<article id="dimension-${escape(id)}" data-context-item class="min-w-0">
    <h2 class="break-words font-display text-lg font-semibold text-white">${escape(label(id, item))}</h2>
    <section class="dimension-levels" aria-label="Resolution levels">
      <h3 class="ui-section-title">Resolution levels</h3>
      <p class="dimension-levels-description">Resolution levels, from parent to child.</p>
      ${resolutionHierarchy(item.resolutions)}
    </section>
    <p data-dimension-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.description || "No description provided.")}</p></article>`;
  }).join("");
}

export function schemaColumns(config, profile) {
  const grainKeys = new Set(profileGrainKeys(config, profile));
  const producers = new Map();
  const producingOperators = new Map();
  for (const [operatorId, operator] of Object.entries(profile.assembly)) {
    const kind = config.functions[operator.compute.function]?.kind;
    for (const ref of operator.interface.outputs) {
      const id = ref.replace(/^\$features\./, "");
      if (!producers.has(id)) producers.set(id, kind === "escape" ? "escape" : ["vectorize", "collapse"].includes(kind) ? "amber" : "teal");
      if (!producingOperators.has(id)) producingOperators.set(id, new Set());
      producingOperators.get(id).add(operatorId);
    }
  }
  return [
    ...[...grainKeys].map(id => ({ id, ...profile.features[id], role: "Dimension", color: "dimension" })),
    ...Object.entries(profile.features).filter(([id]) => !grainKeys.has(id)).map(([id, feature]) => {
      const color = producers.get(id) || "neutral";
      return { id, ...feature, color, role: color === "teal" ? "Raw" : color === "escape" ? "External" : "Feature" };
    }),
  ].map(column => ({ ...column, operators: [...(producingOperators.get(column.id) || [])] }));
}

function grainCards(config, grain) {
  return grain.map(({ dimension, resolution }) => {
    const dimensionDefinition = config.dimensions[dimension];
    const resolutionDefinition = dimensionDefinition?.resolutions[resolution];
    const resolutionId = resolutionDefinition?.id ?? resolution;
    return `<li class="profile-grain-card" data-grain-dimension="${escape(dimension)}" data-grain-resolution="${escape(resolutionId)}">
      <header class="profile-grain-heading">
        <span class="profile-grain-label">Dimension</span>
        <h4>${escape(dimensionDefinition?.name || dimension)}</h4>
      </header>
      <dl class="profile-grain-fields">
        <div><dt>Resolution</dt><dd><code>${escape(resolutionId)}</code></dd></div>
        <div><dt>Data key</dt><dd><code>${escape(resolutionDefinition?.key || resolution)}</code></dd></div>
        <div><dt>Data type</dt><dd>${dataTypeLabel(resolutionDefinition?.type)}</dd></div>
      </dl>
    </li>`;
  }).join("");
}

function profileOperatorCards(config, profile, operators) {
  const featureList = references => references.length
    ? references.map(reference => `<code>${escape(reference.replace(/^\$features\./, ""))}</code>`).join("")
    : '<span class="profile-operator-empty">None declared</span>';
  return `<div class="profile-operator-list">${operators.map(([id, operator]) => {
    const functionId = operator.compute.function;
    const fn = config.functions[functionId] || {};
    const args = Object.entries(operator.compute.args || {});
    return `<article class="profile-operator" data-profile-operator="${escape(id)}" data-operator-kind="${escape(fn.kind)}">
      <header class="profile-operator-header">
        <span class="profile-operator-symbol">${kindIcon(fn.kind, "profile-operator-icon")}</span>
        <div class="profile-operator-identity"><span class="profile-operator-label">OPERATOR</span><h4>${escape(id)}</h4></div>
        ${badge(fn.kind || "Unspecified", fn.kind === "escape" ? "violet" : "neutral")}
      </header>
      ${args.length ? `<details class="profile-operator-bindings"><summary>Argument bindings <span>${args.length}</span></summary>
        <div class="ui-table-scroll" tabindex="0" role="region" aria-label="Argument bindings for ${escape(id)}"><table class="ui-table"><caption class="sr-only">Argument bindings for ${escape(id)}</caption>
          <thead><tr><th scope="col">Argument</th><th scope="col">Binding</th></tr></thead>
          <tbody>${args.map(([name, value]) => `<tr><th scope="row">${escape(name)}</th><td><code>${display(value)}</code></td></tr>`).join("")}</tbody>
        </table></div></details>` : ""}
      <div class="profile-operator-function"><span class="profile-operator-label">Function</span>
        <a href="${href("functions", `function-${functionId}`)}">${escape(fn.name || functionId)}</a>
        ${fn.name && fn.name !== functionId ? `<code>${escape(functionId)}</code>` : ""}
      </div>
      <dl class="profile-operator-contract">
        <div><dt>Input features</dt><dd>${featureList(operator.interface.inputs)}</dd></div>
        <div><dt>Output features${fn.kind === "escape" ? " (logical)" : ""}</dt><dd>${featureList(operator.interface.outputs)}</dd></div>
      </dl>
      ${fn.kind === "collapse" ? `<div class="profile-operator-note">Group by grain keys: <code>${display(profileGrainKeys(config, profile))}</code></div>` : ""}
      ${fn.kind === "escape" ? '<div class="profile-operator-note">External effects are uncontrolled. Declared inputs and outputs express logical dependencies only; escape outputs are not materialized as dataframe columns.</div>' : ""}
    </article>`;
  }).join("")}</div>`;
}

function profileCards(config) {
  return profiles(config).map(({ id, profile }) => {
    const columns = schemaColumns(config, profile);
    const grain = profile.grain;
    const operators = Object.entries(profile.assembly);
    return `<article id="profile-${escape(id)}" data-context-item>
      <div hidden>
        <h2>${escape(label(id, profile))}</h2>
        ${profile.description ? `<p data-profile-description>${escape(profile.description)}</p>` : ""}
      </div>
      <section aria-label="Profile details">
        <div class="space-y-6">
          ${grain.length ? `<div>${subheading("Grain")}<ul class="profile-grain-grid">${grainCards(config, grain)}</ul></div>` : ""}
          ${profile.scope || profile.order?.length ? `<div class="grid gap-6 ${profile.scope && profile.order?.length ? "md:grid-cols-2" : ""}" data-profile-context>
          ${profile.scope ? `<div class="min-w-0">${subheading("Scope")}${description(profile.scope)}</div>` : ""}
          ${profile.order?.length ? `<div class="min-w-0">${subheading("Logical order")}<p class="mt-2 text-xs text-slate-500">Not a physical row-order guarantee.</p>${chips(profile.order.map(key => {
            const dimensionId = key.dimension;
            const dimension = config.dimensions[dimensionId];
            const resolution = dimension?.resolutions[key.resolution];
            return `${dimension?.name || dimensionId} · ${resolution?.key || key.resolution} ${key.direction}`;
          }))}</div>` : ""}</div>` : ""}
          <div>${subheading("Produced schema")}<div class="ui-table-scroll profile-schema-scroll" tabindex="0" role="region" aria-label="${escape(label(id, profile))} produced schema">
        <table data-dataset-schema="${escape(id)}" class="ui-table profile-schema-table">
          <caption class="sr-only">Produced schema for ${escape(label(id, profile))}: declared column types and units; no sample records.</caption>
          <colgroup><col class="profile-schema-name-col"><col class="profile-schema-role-col"><col class="profile-schema-unit-col"><col class="profile-schema-operator-col"></colgroup>
          <thead><tr>${["Column", "Role", "Unit", "Producing operator"].map(title => `<th scope="col">${title}</th>`).join("")}</tr></thead>
          <tbody>${columns.map(column => `<tr data-schema-column="${escape(column.id)}">
            <th scope="row">${typedName(label(column.id, column), column.type)}${label(column.id, column) !== column.id ? `<span class="profile-schema-column-id">${escape(column.id)}</span>` : ""}</th>
            <td>${badge(column.role, { dimension: "blue", teal: "green", amber: "amber", escape: "violet" }[column.color])}</td>
            <td class="profile-schema-unit">${escape(column.unit || "—")}</td>
            <td>${column.operators.length ? column.operators.map(operator => `<code class="profile-schema-operator">${escape(operator)}</code>`).join("") : '<span class="text-slate-500">None declared</span>'}</td>
          </tr>`).join("")}</tbody>
        </table></div></div>
          ${operators.length ? `<div>${subheading("Assembly")}${profileOperatorCards(config, profile, operators)}</div>` : ""}
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
          <section class="min-w-0">${subheading("Operation diagram")}<div class="mt-3 flex min-h-40 items-center justify-center overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-5">${miniGraphic(kind)}</div></section></div>
        ${(fn.doc?.examples || []).slice(1).map((example, index) => `<section class="mt-6">${subheading(`Example ${index + 2}`)}<pre class="mt-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 p-5 font-mono text-xs leading-6 text-slate-300"><code class="language-python">${escape(example)}</code></pre></section>`).join("")}
        ${fn.kind === "escape" ? `<p class="mt-10 text-sm leading-6 text-violet-200/90">Uncontrolled external operation: declared feature inputs and outputs express logical dependencies only. Dataframes are passed only through explicitly bound arguments, and the return value is ignored.</p>
          ${fn.escape_operators?.length ? `<div class="mt-10">${subheading("Used by operators")}${fn.escape_operators.map(operator => `<div class="py-4">
            <p class="font-mono text-xs text-slate-200">${escape(operator.profile)} · ${escape(operator.operator)}</p>
            <p class="mt-2 font-mono text-xs text-slate-400">Declared inputs: ${escape(operator.inputs.join(", ") || "none")}</p>
            <p class="mt-1 font-mono text-xs text-slate-400">Declared outputs: ${escape(operator.outputs.join(", ") || "none")}</p></div>`).join("")}</div>` : ""}` : ""}
        ${Object.keys(fn.args || {}).length ? `<div class="mt-10">${subheading("Arguments")}
          <div class="ui-table-scroll mt-3" tabindex="0" role="region" aria-label="Arguments for ${escape(fn.name || id)}">
            <table class="ui-table function-arguments-table">
              <caption class="sr-only">Arguments for ${escape(fn.name || id)} with their data types and descriptions</caption>
              <thead><tr><th scope="col">Argument</th><th scope="col">Description</th></tr></thead>
              <tbody>${Object.entries(fn.args).map(([key, arg]) => `<tr>
                <th scope="row">${typedName(key, arg.type)}</th>
                <td>${escape(fn.doc?.params?.[key] || arg.comment || "—")}</td>
              </tr>`).join("")}</tbody>
            </table>
          </div></div>` : ""}
        ${fn.doc?.returns || fn.return_type ? `<div class="mt-10">${subheading("Returns")}${fn.return_type ? `<p class="mt-3 flex flex-wrap items-center gap-2 text-lime-300"><span aria-hidden="true">-&gt;</span>${dataTypeLabel(fn.return_type)}</p>` : ""}${fn.doc?.returns ? description(fn.doc.returns) : ""}</div>` : ""}
        ${fn.doc?.raises?.length ? `<div class="mt-10">${subheading("Raises")}<ul class="mt-3 space-y-2">${fn.doc.raises.map(error => `<li class="text-sm leading-6 text-slate-400"><span class="font-mono text-amber-300">${escape(error.type)}</span> — ${escape(error.description)}</li>`).join("")}</ul></div>` : ""}
        ${fn.entrypoint || fn.signature_validation_disabled ? `<div class="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-slate-800/60 pt-5">
          <span class="break-all font-mono text-xs text-slate-400">${escape(fn.entrypoint)}</span>${fn.signature_validation_disabled ? badge("Python signature validation disabled", "amber") : ""}</div>` : ""}
      </article>`).join("")}</div></div>`).join("");
}

export function stageCards(data) {
  return data.stages.map(stage => `<section id="stage-${stage.stage}" data-context-item>
    <div class="mb-3 flex items-center gap-3"><h2 class="rounded-lg bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">Stage ${stage.stage}</h2>
      <span class="font-mono text-[10px] uppercase tracking-wider text-slate-500">${stage.steps.length} invocation${stage.steps.length === 1 ? "" : "s"}</span></div>
    <div class="grid grid-cols-1 gap-10">${stage.steps.map(step => `<div>
      <h3 class="mb-2 break-words font-display text-lg font-semibold text-white">${escape(step.title)}</h3><article>
        <dl class="grid overflow-hidden rounded-lg border border-slate-800 bg-slate-950/55 font-mono text-xs md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_10rem]">
          ${[["Function kind", step.function_kind, "text-amber-200"], ["Function", step.function_label, "text-white"],
            [step.uncontrolled ? "Declared logical outputs" : "Profile feature output", step.feature || "None", "text-cyan-200"],
            [step.uncontrolled ? "Python return (ignored)" : "Returns", step.returns.type.engine || "—", "text-lime-300"]].map(([title, value, color]) => `<div class="min-w-0 border-b border-slate-800 p-3 md:border-r">
              <dt class="mb-1 uppercase tracking-wider text-slate-500">${title}</dt><dd class="break-all ${color}">${title.toLowerCase().includes("return") ? dataTypeLabel(value) : escape(value)}</dd></div>`).join("")}
          <div class="min-w-0 p-3 md:col-span-4"><dt class="mb-1 uppercase tracking-wider text-slate-500">Depends on invocations</dt>
            <dd class="flex flex-wrap gap-1.5">${step.depends_on_invocations.map(dep => `<span class="rounded-md bg-slate-950/70 px-2 py-1 text-slate-300">${escape(dep.function)}</span>`).join("") || '<span class="text-slate-400">No invocation dependencies</span>'}</dd></div>
        </dl>
        ${step.dataset_label ? `<p class="mt-3 font-mono text-xs text-slate-500">Profile: ${escape(step.dataset_label)}</p>` : ""}
        ${step.uncontrolled ? `<p class="mt-3 rounded-lg border border-violet-900/60 bg-violet-950/30 p-3 text-xs leading-5 text-violet-200">Uncontrolled external operation. Declared inputs: ${escape(step.input_features.join(", ") || "none")}. Declared outputs: ${escape(step.output_features.join(", ") || "none")}. These are logical dependencies only; dataframes are passed only through explicit arguments, and escape return values are ignored.</p>` : ""}
        ${step.row_context !== null ? `<div class="mt-3 font-mono text-xs text-slate-400">Row context: ${display(step.row_context)}</div>` : ""}
        ${Object.keys(step.args).length ? `<div class="ui-table-scroll mt-5" tabindex="0" role="region" aria-label="Argument bindings for ${escape(step.title)}"><table class="ui-table">
          <caption class="sr-only">Argument bindings for ${escape(step.title)}</caption>
          <thead><tr>${["Argument", "Value"].map(title => `<th scope="col">${title}</th>`).join("")}</tr></thead>
          <tbody>${Object.entries(step.args).map(([id, arg]) => `<tr><th scope="row">${typedName(id, arg.type.engine || arg.type.function || "—")}</th>
            <td><code>${display(arg.value)}</code></td></tr>`).join("")}</tbody>
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
    content: page(`<section id="${view}" class="mb-16">
      ${view === "stages" ? '<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Execution plan</p>' : ""}
      ${view === "dimensions" ? '<p data-dimension-label class="dimension-detail-label" hidden>Dimension</p>' : ""}
      ${heading(title, descriptions[view] ?? null, view, view === "features" ? features(config).length : null)}
      ${catalogOverview(data, view)}<div class="space-y-8">${renderers[view]()}</div></section>`),
  };
}
