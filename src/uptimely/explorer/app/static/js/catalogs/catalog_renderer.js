import { KINDS, contextHeader, contextLink, display, distribution, escape, heading, href, icon, kindIcon, miniGraphic, page, statistic } from "../rendering/shared_markup.js";

export function datasets(configuration) {
  return Object.entries(configuration.entities).flatMap(([entityId, entity]) =>
    Object.entries(entity.datasets).map(([id, dataset]) => ({ id, dataset, entityId, entity })));
}

export function features(configuration) {
  return datasets(configuration).flatMap(item => {
    const produced = new Map();
    for (const [actionId, action] of Object.entries(item.dataset.actions)) {
      for (const reference of action.features.outputs) {
        const id = reference.replace(/^\$features\./, "");
        if (!item.entity.dimensions.includes(id)) {
          produced.set(id, { ...item, featureId: id, feature: item.dataset.features[id], actionId, action });
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
const subheading = title => `<h3 class="font-mono text-xs font-semibold uppercase tracking-[.16em] text-slate-300">${escape(title)}</h3>`;
const chips = values => `<div class="mt-3 flex flex-wrap gap-2">${values.map(value =>
  `<span class="rounded-md bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">${escape(value)}</span>`).join("")}</div>`;

const contextLinks = {
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    return datasets(config).map(({ id, dataset }) => {
      const items = produced.filter(item => item.id === id);
      return items.length ? group(label(id, dataset), items.map(item =>
        contextLink(`feature-${id}-${item.featureId}`, label(item.featureId, item.feature), "features"))) : "";
    }).join("");
  },
  datasets(data) {
    return Object.entries(data.catalogs.configuration.entities).map(([id, entity]) => group(label(id, entity),
      Object.entries(entity.datasets).map(([datasetId, dataset]) =>
        contextLink(`dataset-${datasetId}`, label(datasetId, dataset), "datasets")))).join("");
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
  entities(data) {
    return Object.entries(data.catalogs.configuration.entities).map(([id, item]) =>
      contextLink(`entity-${id}`, label(id, item), "entities")).join("");
  },
  dimensions(data) {
    return Object.entries(data.catalogs.configuration.dimensions).map(([id, item]) =>
      contextLink(`dimension-${id}`, label(id, item), "dimensions")).join("");
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
  entities(data) {
    const { configuration: config, summary } = data.catalogs;
    const entities = Object.values(config.entities);
    const counts = new Map();
    entities.forEach(entity => {
      const key = `${entity.dimensions.length} dimensions`;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    const withDatasets = entities.filter(entity => Object.keys(entity.datasets).length).length;
    return {
      stats: [["Entities", summary.entity_count], ["With datasets", withDatasets, "datasets"],
        ["Datasets", summary.dataset_count], ["Dimensions", summary.dimension_count]],
      charts: [distribution("Entities by dimension count", [...counts])],
    };
  },
  datasets(data) {
    const { configuration: config, summary } = data.catalogs;
    const entities = Object.entries(config.entities);
    const withDatasets = entities.filter(([, entity]) => Object.keys(entity.datasets).length).length;
    return {
      stats: [["Datasets", summary.dataset_count], ["Owning entities", withDatasets, "entities"],
        ["Features", datasets(config).reduce((total, { dataset }) => total + Object.keys(dataset.features).length, 0)],
        ["Actions", summary.action_count, "invocations"]],
      charts: [distribution("Datasets by entity", entities.map(([id, entity]) =>
        [id, Object.keys(entity.datasets).length]))],
    };
  },
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    return {
      stats: [["Features", produced.length],
        ["Datasets with features", new Set(produced.map(item => item.id)).size, "datasets"]],
      charts: [distribution("Features by dataset", datasets(config).map(({ id }) =>
        [id, produced.filter(item => item.id === id).length]))],
    };
  },
  dimensions(data) {
    const { configuration: config, summary } = data.catalogs;
    const dimensions = Object.values(config.dimensions);
    const types = new Map();
    dimensions.forEach(item => types.set(item.type, (types.get(item.type) || 0) + 1));
    const roots = dimensions.filter(item => !item.parent).length;
    return {
      stats: [["Dimensions", summary.dimension_count], ["Types", types.size, "dimensions"],
        ["Root dimensions", roots, "dimensions"],
        ["Child dimensions", summary.dimension_count - roots, "dimensions"]],
      charts: [distribution("Dimensions by type", [...types])],
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
        ["Entity", label(item.entityId, item.entity), "entities", href("entities", `entity-${item.entityId}`)],
        ["Dataset", label(item.id, item.dataset), "datasets", href("datasets", `dataset-${item.id}`)],
        ["Type", item.feature.type || "unspecified", "features"],
        ["Unit", item.feature.unit || "Not specified", "dimensions"],
      ].map(([title, value, key, url]) => `<div><dt class="flex items-center gap-2 text-xs text-slate-500">${icon(key, "h-3.5 w-3.5")}${title}</dt>
        <dd class="mt-2 break-words font-mono text-sm text-slate-300">${url ? `<a href="${url}">${escape(value)}</a>` : escape(value)}</dd></div>`).join("")}</dl>
      ${fn.kind === "escape" ? '<p class="mt-6 text-sm leading-6 text-violet-300">Declared logical output only; escape outputs are not materialized as dataframe columns.</p>' : ""}
    </article>`;
  }).join("");
}

function entityCards(config) {
  return Object.entries(config.entities).map(([id, entity]) => `<article id="entity-${escape(id)}" data-context-item>
    <p class="font-mono text-[10px] uppercase tracking-wider text-slate-500">${escape(id)}</p>
    <h2 class="mt-1 font-display text-xl font-semibold text-white">${escape(label(id, entity))}</h2>${entity.description ? description(entity.description) : ""}
    <div class="mt-4">${subheading("Dimensions")}${chips(entity.dimensions.map(key => config.dimensions[key].name || key))}</div>
    <div class="mt-4 border-t border-slate-800 pt-3">${subheading("Datasets")}
      <ul class="mt-3 space-y-1">${Object.entries(entity.datasets).map(([key, dataset]) =>
        `<li class="font-mono text-sm text-cyan-200"><a href="${href("datasets", `dataset-${key}`)}">${escape(label(key, dataset))}</a></li>`).join("")}</ul>
    </div></article>`).join("");
}

function dimensionCards(config) {
  return Object.entries(config.dimensions).map(([id, item]) => `<article id="dimension-${escape(id)}" data-context-item class="min-w-0">
    ${itemTitle(id, item, "h2", "text-lg")}${chips([item.type, ...(item.parent ? [`child of ${config.dimensions[item.parent].name || item.parent}`] : [])])}
    ${description(item.description)}</article>`).join("");
}

export function schemaColumns(config, entity, dataset) {
  const producers = new Map();
  for (const action of Object.values(dataset.actions)) {
    const kind = config.functions[action.binding.function]?.kind;
    for (const ref of action.features.outputs) {
      const id = ref.replace(/^\$features\./, "");
      if (!producers.has(id)) producers.set(id, kind === "escape" ? "escape" : ["vectorize", "collapse"].includes(kind) ? "amber" : "teal");
    }
  }
  return [
    ...entity.dimensions.map(id => ({ id, ...config.dimensions[id], role: "Dimension", color: "dimension" })),
    ...Object.entries(dataset.features).filter(([id]) => !entity.dimensions.includes(id)).map(([id, feature]) => {
      const color = producers.get(id) || "neutral";
      return { id, ...feature, color, role: color === "teal" ? "Raw" : color === "escape" ? "External" : "Feature" };
    }),
  ];
}

function datasetCards(config) {
  const colors = {
    dimension: "bg-[#172b46] text-[#b5d4f8]", teal: "bg-[#15352e] text-[#a5dfca]",
    escape: "bg-[#30234a] text-[#d8b4fe]", amber: "bg-[#392e19] text-[#efcf89]",
    neutral: "bg-slate-800 text-slate-300",
  };
  return datasets(config).map(({ id, dataset, entityId, entity }) => {
    const columns = schemaColumns(config, entity, dataset);
    const actions = Object.entries(dataset.actions).filter(([, action]) => config.functions[action.binding.function]?.kind !== "vectorize");
    return `<article id="dataset-${escape(id)}" data-context-item>
      <header class="flex flex-wrap items-start justify-between gap-4"><div>
        <p class="font-mono text-[10px] uppercase tracking-wider text-slate-500">${escape(label(entityId, entity))}</p>
        ${itemTitle(id, dataset, "h2", "text-xl")}</div><span class="rounded-full bg-slate-800/70 px-3 py-1 font-mono text-[10px] text-slate-400">${columns.length} columns</span></header>
      <section class="mt-5 border-t border-slate-800 pt-5" aria-label="Dataset details">
        <h3 class="font-display text-lg font-semibold text-white">Dataset details</h3>
        <div class="mt-5 space-y-6">${dataset.description ? description(dataset.description) : ""}
          <dl class="grid gap-6 sm:grid-cols-2">${["filtering", "coverage"].filter(key => dataset.row_scope?.[key]).map(key => `<div>
            <dt class="font-mono text-xs uppercase tracking-wider text-slate-400">${key}</dt>
            <dd class="mt-2 text-sm leading-6 text-slate-300">${escape(dataset.row_scope[key])}</dd></div>`).join("")}</dl>
          ${dataset.order?.length ? `<div>${subheading("Logical order")}<p class="mt-2 text-xs text-slate-500">Not a physical row-order guarantee.</p>${chips(dataset.order.map(key =>
            `${config.dimensions[key.dimension.replace(/^\$dimensions\./, "")]?.name || key.dimension} ${key.direction}`))}</div>` : ""}
          ${actions.length ? `<div>${subheading("Actions")}<div class="mt-3 divide-y divide-slate-800">${actions.map(([key, action]) => {
            const fn = config.functions[action.binding.function] || {};
            return `<div class="space-y-2 py-3"><p class="font-mono text-sm text-slate-300">${escape(fn.kind)} · ${escape(fn.name || action.binding.function)}</p>
              <p class="font-mono text-xs text-slate-500">${escape(key)} · ${escape(action.binding.function)}</p>
              ${fn.kind === "collapse" ? `<p class="font-mono text-xs text-slate-400">Input dataset inferred from bound features · Group by entity dimensions: ${display(entity.dimensions)}<br>${escape(fn.name || action.binding.function)}(${display(action.binding.args)})</p>` : ""}
              ${fn.kind === "escape" ? '<p class="text-xs leading-5 text-violet-300">External effects are uncontrolled. Declared inputs and outputs express logical dependencies only; escape outputs are not materialized as dataframe columns.</p>' : ""}</div>`;
          }).join("")}</div></div>` : ""}
        </div></section>
      ${dataset.row_scope?.grain ? description(dataset.row_scope.grain) : ""}
      <div class="mt-6"><div class="dataset-table-scroll overflow-x-auto rounded-xl border border-slate-700/60">
        <table data-dataset-schema="${escape(id)}" class="w-full min-w-max border-collapse text-left font-mono text-xs">
          <caption class="sr-only">Declared column types and units for ${escape(label(id, dataset))}; schema only, no sample records.</caption>
          <thead><tr>${columns.map(column => `<th scope="col" class="border-b border-slate-700/50 px-4 py-4 ${colors[column.color]}">${escape(label(column.id, column))}
            <span class="mt-2 block text-[10px] font-normal">${column.role}</span><span class="mt-1 block text-[9px] font-normal text-slate-500">${escape(column.id)}</span></th>`).join("")}</tr></thead>
          <tbody><tr>${columns.map(column => `<td class="border-b border-slate-800/60 px-4 py-3 text-lime-300">${escape(column.type || "unspecified")}</td>`).join("")}</tr>
            <tr>${columns.map(column => `<td class="px-4 py-3 text-slate-400">${escape(column.unit || "—")}</td>`).join("")}</tr></tbody>
        </table></div></div></article>`;
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
            <p class="font-mono text-xs text-slate-200">${escape(action.entity)} / ${escape(action.dataset)} · ${escape(action.action)}</p>
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
            [step.uncontrolled ? "Declared logical outputs" : "Dataset feature output", step.feature || "None", "text-cyan-200"],
            [step.uncontrolled ? "Python return (ignored)" : "Returns", step.returns.type.engine || "—", "text-lime-300"]].map(([title, value, color]) => `<div class="min-w-0 border-b border-slate-800 p-3 md:border-r">
              <dt class="mb-1 uppercase tracking-wider text-slate-500">${title}</dt><dd class="break-all ${color}">${escape(value)}</dd></div>`).join("")}
          <div class="min-w-0 p-3 md:col-span-4"><dt class="mb-1 uppercase tracking-wider text-slate-500">Depends on invocations</dt>
            <dd class="flex flex-wrap gap-1.5">${step.depends_on_invocations.map(dep => `<span class="rounded-md bg-slate-950/70 px-2 py-1 text-slate-300">${escape(dep.function)}</span>`).join("") || '<span class="text-slate-400">No invocation dependencies</span>'}</dd></div>
        </dl>
        ${step.dataset_label ? `<p class="mt-3 font-mono text-xs text-slate-500">Dataset: ${escape(step.dataset_label)}</p>` : ""}
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
  const renderers = { features: () => featureCards(config), entities: () => entityCards(config),
    dimensions: () => dimensionCards(config), datasets: () => datasetCards(config),
    functions: () => functionCards(data), stages: () => stageCards(data) };
  const title = view[0].toUpperCase() + view.slice(1);
  const descriptions = {
    functions: "Browse the function catalog, argument types, return signatures, and source entrypoints.",
    dimensions: "Inspect the dimensions that define data grain and their parent relationships.",
    features: "",
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
