import { badge, contextGroup as group, contextHeader, contextLink, dataTypeLabel, display, distribution, escape, heading, href, icon, kindIcon, page, statistic, typedName } from "../rendering/shared_markup.js";

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

const SOURCE_FEATURE_KINDS = new Set(["read", "conform", "expand", "collapse"]);
const featureReferenceId = reference => reference.startsWith("$features.")
  ? reference.slice("$features.".length)
  : null;
const operatorInputs = operator => operator.interface.inputs || [];
const label = (id, value) => value.name || id;
const operatorLabel = (id, operator) => operator.name || id.replace(/[_-]+/g, " ").replace(/\b\w/g, character => character.toUpperCase());
const description = value => `<p class="mt-4 text-sm leading-6 text-slate-400">${escape(value || "No description provided.")}</p>`;
const dimensionResolutionTarget = (dimensionId, resolutionId) =>
  `dimension-resolution-${dimensionId}-${resolutionId}`;
const itemTitle = (id, item, tag = "h2", size = "text-2xl", type = null, showId = true) => `<${tag} class="break-words font-display ${size} font-semibold text-white">${type === null ? escape(label(id, item)) : typedName(label(id, item), type)}</${tag}>${item.name && showId ? `<p class="mt-1 font-mono text-xs text-slate-500">${escape(id)}</p>` : ""}`;
const subheading = (title, iconKey = null) => iconKey
  ? `<h3 class="ui-section-title profile-detail-subheading">${icon(iconKey, "profile-detail-icon")}<span>${escape(title)}</span></h3>`
  : `<h3 class="ui-section-title">${escape(title)}</h3>`;
const profileGrain = (config, grain) => grain.map(({ dimension, resolution }) => {
  const dimensionDefinition = config.dimensions[dimension];
  const resolutionDefinition = dimensionDefinition?.resolutions[resolution];
  return {
    dimension: dimensionDefinition?.name || dimension,
    resolution: label(resolutionDefinition?.id ?? resolution, resolutionDefinition || {}),
  };
});
const profileGrainMarkup = (grain, resolutionsOnly = false) => grain.length
  ? `<ul class="profile-summary-grain-list${resolutionsOnly ? " profile-summary-grain-resolutions" : ""}">${grain.map(({ dimension, resolution }) => `<li class="profile-summary-grain-path" aria-label="${escape(`${dimension} dimension at ${resolution} resolution`)}">
      <span class="profile-summary-grain-badge profile-summary-grain-resolution">${icon("resolutions", "profile-summary-grain-icon")}<code>${escape(resolution)}</code></span>
      ${resolutionsOnly ? "" : `<i class="profile-summary-grain-relation" data-lucide="at-sign" aria-hidden="true"></i>
      <span class="profile-summary-grain-badge profile-summary-grain-dimension">${icon("dimensions", "profile-summary-grain-icon")}<strong>${escape(dimension)}</strong></span>`}
    </li>`).join("")}</ul>`
  : '<span class="profile-summary-grain-empty">No grain defined</span>';
const chip = (value, isType = false) => isType
  ? dataTypeLabel(value, "rounded-md bg-slate-800 px-2.5 py-1 text-slate-300")
  : `<span class="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">${escape(value)}</span>`;
const chips = values => `<div class="mt-3 flex flex-wrap gap-2">${values.map(value =>
  chip(value)).join("")}</div>`;

function orderedResolutions(resolutions) {
  const entries = Object.entries(resolutions).map(([key, resolution]) => ({
    id: resolution.id ?? key, resolution,
  }));
  const byId = new Map(entries.map(entry => [entry.id, entry]));
  const visited = new Set();
  const ordered = [];
  const visit = entry => {
    if (visited.has(entry.id)) return;
    visited.add(entry.id);
    const parent = byId.get(entry.resolution.parent);
    if (parent) visit(parent);
    ordered.push(entry);
  };
  entries.forEach(visit);
  return ordered;
}

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
      .map(([category, items]) => group(category,
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
      const resolutions = orderedResolutions(item.resolutions).map(({ id: resolutionId, resolution }) => {
        return contextLink(
          dimensionResolutionTarget(id, resolutionId), label(resolutionId, resolution), "resolutions",
        );
      }).join("");
      return `<div class="dimension-context-group">
        ${contextLink(`dimension-${id}`, label(id, item), "dimensions")}
        <div class="dimension-context-resolutions" role="group" aria-label="${escape(`${label(id, item)} resolutions`)}">
          ${resolutions}
        </div>
      </div>`;
    }).join("");
  },
};

export function catalogContext(data, view) {
  const links = contextLinks[view](data);
  const title = view[0].toUpperCase() + view.slice(1);
  return `<aside class="site-context" id="catalog-context" aria-label="${title} context" data-context-label="${view}">
    ${contextHeader(title, view, "catalog-context")}
    <nav class="context-links" aria-label="${title} on this page">${contextLink(
      "overview", "Overview", "overview",
    )}
      <hr class="context-separator">${links || `<p class="context-empty">No ${view}.</p>`}
    </nav></aside>`;
}

const overviewData = {
  features(data) {
    const config = data.catalogs.configuration;
    const produced = features(config);
    const summary = data.catalogs.summary;
    const typeCounts = new Map();
    produced.forEach(({ feature }) => {
      const type = feature.type || "unspecified";
      typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
    });
    return {
      stats: [],
      charts: [distribution("Features by role",
        ["input", "intermediate", "output"].map(key => [key, summary.feature_buckets[key] || 0]),
        { iconLabels: true, tooltip: "Inputs are source features counted per profile. Intermediate features are used by another calculation; other calculated features are outputs." }),
        distribution("Features by data type", [...typeCounts], { typeLabels: true })],
    };
  },
  dimensions(data) {
    const config = data.catalogs.configuration;
    const dimensions = Object.values(config.dimensions);
    const resolutions = dimensions.flatMap(item => Object.values(item.resolutions));
    const types = new Map();
    resolutions.forEach(item => types.set(item.type, (types.get(item.type) || 0) + 1));
    return {
      stats: [],
      charts: [
        distribution("Resolutions by type", [...types], { typeLabels: true }),
        distribution("Resolutions by dimension", Object.entries(config.dimensions).map(([id, item]) =>
          [label(id, item), Object.keys(item.resolutions).length]), { dimensionLabels: true }),
      ],
    };
  },
  stages(data) {
    return {
      stats: [],
      charts: [
        distribution("Invocations by stage",
          data.stages.map(stage => [`Stage ${stage.stage}`, stage.steps.length])),
      ],
    };
  },
};

function catalogOverview(data, view) {
  if (view === "profiles") return profileOverview(data);
  if (view === "functions") return functionOverview(data);
  const { stats, charts } = overviewData[view](data);
  const title = view[0].toUpperCase() + view.slice(1);
  const ariaLabel = view === "dimensions" ? "Dimension resolution charts" : `${title} overview`;
  return `<section id="overview" data-context-item aria-label="${ariaLabel}" class="mb-12">
    ${["features", "dimensions", "stages"].includes(view) ? "" : `<h2 class="ui-section-title mb-6">${title} overview</h2>`}
    ${stats.length ? `<div class="grid gap-3 sm:grid-cols-2${stats.length > 2 ? " lg:grid-cols-4" : ""}">${stats.map(args => statistic(...args)).join("")}</div>` : ""}
    <div class="catalog-charts${["features", "dimensions"].includes(view) ? " lg:grid-cols-2" : ""}">${charts.join("")}</div>
  </section>`;
}

function profileOverview(data) {
  const config = data.catalogs.configuration;
  const profileItems = profiles(config);
  const maximumOperators = Math.max(
    0, ...profileItems.map(({ profile }) => Object.keys(profile.assembly).length),
  );
  const cards = profileItems.map(({ id, profile }) => {
    const operatorCount = Object.keys(profile.assembly).length;
    const grain = profileGrain(config, profile.grain);
    const width = maximumOperators ? operatorCount / maximumOperators * 100 : 0;
    return `<a class="profile-summary-card" href="#profile-${encodeURIComponent(id)}"
      aria-label="${escape(`${label(id, profile)}: ${operatorCount} operator${operatorCount === 1 ? "" : "s"}`)}">
      <header class="profile-summary-header">
        <div class="profile-summary-identity">
          <span class="profile-summary-category">${escape(profile.category || "Uncategorized")}</span>
          <h3>${escape(label(id, profile))}</h3>
        </div>
      </header>
      <div class="profile-summary-scale">
        <div class="profile-summary-meter" role="img" aria-label="${escape(`${operatorCount} operator${operatorCount === 1 ? "" : "s"}; relative profile size`)}">
          <span style="width:${width}%"></span>
        </div>
        <div class="profile-summary-size"><strong>${operatorCount}</strong>${icon("operators", "profile-summary-operator-icon")}</div>
      </div>
      <div class="profile-summary-grain" aria-label="Profile grain">
        ${profileGrainMarkup(grain, true)}
      </div>
    </a>`;
  });
  return `<section id="overview" data-context-item aria-label="Profiles overview" class="mb-12">
    <div class="profile-summary-grid">${cards.join("") || '<p class="text-sm text-slate-400">No profiles are defined.</p>'}</div>
  </section>`;
}

function functionOverview(data) {
  const groups = Object.entries(data.catalogs.function_groups);
  const returnTypeCounts = new Map();
  groups.flatMap(([, items]) => Object.values(items)).forEach(item => {
    const type = item.return_type || item.returns || "unspecified";
    returnTypeCounts.set(type, (returnTypeCounts.get(type) || 0) + 1);
  });
  return `<section id="overview" data-context-item aria-label="Functions overview" class="mb-12">
    <div class="catalog-charts lg:grid-cols-2">${distribution("Functions by category", groups.map(([category, items]) => {
      const count = Object.keys(items).length;
      return [category, count, count ? `#functions-${encodeURIComponent(category)}` : null];
    }), { total: data.catalogs.summary.function_count })}
      ${distribution("Functions by return type", [...returnTypeCounts], { typeLabels: true, returnTypeLabels: true })}</div></section>`;
}

function featureCards(config, invocations) {
  return features(config).map(item => {
    const role = SOURCE_FEATURE_KINDS.has(item.operator.kind) ? "Input"
      : Object.values(item.profile.assembly).some(operator =>
        operator.kind === "vectorize"
        && operatorInputs(operator).some(reference =>
          featureReferenceId(reference) === item.featureId))
        ? "Intermediate" : "Output";
    const grainKeys = new Set(profileGrainKeys(config, item.profile));
    const producedFeatures = new Set(Object.values(item.profile.assembly).flatMap(operator =>
      operator.interface.outputs.map(featureReferenceId).filter(id => id && !grainKeys.has(id))));
    const linkedFeatures = featureIds => [...new Set(featureIds)]
      .filter(id => id !== item.featureId)
      .map(id => {
        const feature = item.profile.features[id] || {};
        const title = label(id, feature);
        return producedFeatures.has(id)
          ? `<a class="feature-lineage-link" href="${href("features", `feature-${item.id}-${id}`)}">${escape(title)}</a>`
          : `<span class="feature-lineage-link">${escape(title)}</span>`;
      });
    const consumers = Object.values(item.profile.assembly).flatMap(operator =>
      operatorInputs(operator).some(reference => featureReferenceId(reference) === item.featureId)
        ? operator.interface.outputs.map(featureReferenceId).filter(Boolean)
        : []);
    return `<article id="feature-${escape(item.id)}-${escape(item.featureId)}" data-context-item>
      ${itemTitle(item.featureId, item.feature, "h2", "text-2xl", item.feature.type || "unspecified", false)}
      <dl class="feature-meta">
        <div><dt>Role</dt><dd>${badge(role, role === "Input" ? "blue" : role === "Intermediate" ? "amber" : "green")}</dd></div>
        <div><dt>Data type</dt><dd>${dataTypeLabel(item.feature.type || "unspecified", "feature-meta-type")}</dd></div>
        <div><dt>Unit</dt><dd><span class="feature-meta-unit">${escape(item.feature.unit || "Not specified")}</span></dd></div>
        <div><dt>Profile</dt><dd><a class="feature-meta-profile" href="${href("profiles", `profile-${item.id}`)}">${icon("profiles", "feature-detail-icon")}<span>${escape(label(item.id, item.profile))}</span></a></dd></div>
      </dl>
      <p data-feature-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.feature.description || "No description provided.")}</p>
      ${item.operator.kind === "escape" ? '<p class="mt-6 text-sm leading-6 text-violet-300">Declared logical output only; escape outputs are not materialized as dataframe columns.</p>' : ""}
      <section class="mt-6" aria-label="Producing operator">
        ${subheading("Produced by operator", "assembly")}
        ${profileOperatorCards(config, item.id, item.profile, [[item.operatorId, item.operator]], invocations, `feature-${item.featureId}-operator`)}
      </section>
      <section class="mt-6" aria-label="Used by feature">
        ${subheading("Used by feature", "output")}
        <div class="feature-lineage-links">${linkedFeatures(consumers).join("") || '<span class="feature-lineage-empty">None declared</span>'}</div>
      </section>
    </article>`;
  }).join("");
}

function resolutionHierarchy(resolutions, highlightedResolutions = [], dimensionId = null) {
  const highlighted = new Set(highlightedResolutions);
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
    const isHighlighted = highlighted.has(node.id);
    return `<li${dimensionId === null ? "" : ` id="${escape(dimensionResolutionTarget(dimensionId, node.id))}"`} data-resolution-id="${escape(node.id)}" data-parent-resolution="${escape(resolution.parent || "")}">
      <article class="dimension-resolution-card${isHighlighted ? " profile-resolution-highlight" : ""}">
        <h3 class="dimension-resolution-id">${typedName(label(node.id, resolution), type)}</h3>
      </article>
      ${node.children.length ? `<ul class="dimension-resolution-children">${node.children.map(renderNode).join("")}</ul>` : ""}
    </li>`;
  };
  return `<ul aria-label="Resolution hierarchy" class="dimension-resolution-tree">${[...roots, ...nodes].map(node => renderNode(node)).join("")}</ul>`;
}

function profileGrainHierarchies(config, grain) {
  if (!grain.length) return '<span class="profile-summary-grain-empty">No grain defined</span>';

  const dimensions = new Map();
  for (const { dimension, resolution } of grain) {
    if (!dimensions.has(dimension)) dimensions.set(dimension, []);
    const definition = config.dimensions[dimension]?.resolutions[resolution];
    dimensions.get(dimension).push(definition?.id ?? resolution);
  }

  const hierarchies = [...dimensions].map(([id, highlightedResolutions]) => {
    const dimension = config.dimensions[id];
    if (!dimension) return "";
    const name = dimension.name || id;
    return `<section class="profile-grain-dimension" aria-label="${escape(`${name} resolution hierarchy`)}">
      <h4 class="profile-grain-dimension-name">${icon("dimensions", "profile-detail-icon")}<span>${escape(name)}</span></h4>
      ${resolutionHierarchy(dimension.resolutions, highlightedResolutions)}
    </section>`;
  }).join("");
  return `<div class="profile-grain-hierarchies">${hierarchies}</div>`;
}

function dimensionCards(config) {
  return Object.entries(config.dimensions).map(([key, item]) => {
    const id = item.id ?? key;
    const usages = Object.entries(config.profiles || {}).flatMap(([profileId, profile]) => {
      const resolutions = profile.grain
        .filter(grain => grain.dimension === key)
        .map(grain => {
          const resolution = item.resolutions[grain.resolution];
          const resolutionId = resolution?.id ?? grain.resolution;
          return { id: resolutionId, name: label(resolutionId, resolution || {}) };
        });
      return resolutions.length ? [{ id: profileId, profile, resolutions }] : [];
    });
    return `<article id="dimension-${escape(id)}" data-context-item class="min-w-0">
    <h2 class="break-words font-display text-lg font-semibold text-white">${escape(label(id, item))}</h2>
    <section class="dimension-levels" aria-label="Resolution levels">
      ${subheading("Resolution levels", "resolutions")}
      <p class="dimension-levels-description">Resolution levels, from parent to child.</p>
      ${resolutionHierarchy(item.resolutions, [], id)}
    </section>
    <section class="function-usage dimension-usage" aria-label="Profile usage">
      ${subheading("Used by profiles", "profiles")}
      <ul class="function-usage-list" data-dimension-usage-list${usages.length ? "" : " hidden"}>${usages.map(({ id: profileId, profile, resolutions }) =>
        `<li class="function-usage-item function-detail-box" data-dimension-profile-usage>
          <a class="function-usage-profile" href="${href("profiles", `profile-${profileId}`)}">${escape(label(profileId, profile))}</a>
          <ul>${resolutions.map(resolution =>
            `<li data-usage-resolution="${escape(resolution.id)}"><span class="function-usage-feature">${icon("resolutions", "profile-summary-grain-icon")} <code>${escape(resolution.name)}</code></span></li>`).join("")}</ul>
        </li>`).join("")}</ul>
      <p class="function-usage-empty" data-dimension-usage-empty${usages.length ? " hidden" : ""}>Not used by any profile.</p>
    </section>
    <p data-dimension-description class="mt-4 text-sm leading-6 text-slate-400">${escape(item.description || "No description provided.")}</p></article>`;
  }).join("");
}

export function schemaColumns(config, profile) {
  const grainKeys = new Set(profileGrainKeys(config, profile));
  const producers = new Map();
  const producingOperators = new Map();
  for (const [operatorId, operator] of Object.entries(profile.assembly)) {
    const kind = operator.kind;
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

function profileOperatorCards(config, profileId, profile, operators, invocations, idPrefix = "operator") {
  const featureList = references => references.length
    ? references.map(reference => {
      const id = reference.replace(/^\$features\./, "");
      return `<code>${escape(label(id, profile.features[id] || {}))}</code>`;
    }).join("")
    : '<span class="profile-operator-empty">None declared</span>';
  const isEngineBound = (value, type) => /\b(?:lazy\s*)?(?:dataframes?|lazyframes?)\b/i.test(type)
    || (typeof value === "string" && (value.startsWith("$params.") || value === "$params"))
    || (Array.isArray(value) && value.some(item => isEngineBound(item, "")))
    || (value !== null && typeof value === "object"
      && Object.values(value).some(item => isEngineBound(item, "")));
  const isReference = value => (typeof value === "string" && value.startsWith("$"))
    || (Array.isArray(value) && value.some(isReference))
    || (value !== null && typeof value === "object"
      && Object.values(value).some(isReference));
  const formatArgumentValue = (value, depth = 0) => {
    if (typeof value === "string") {
      return value.startsWith("$") || depth === 0 ? value : JSON.stringify(value);
    }
    if (Array.isArray(value)) {
      if (!value.length) return "[]";
      const indentation = "  ".repeat(depth + 1);
      return `[\n${indentation}${value.map(item => formatArgumentValue(item, depth + 1)).join(`,\n${indentation}`)}\n${"  ".repeat(depth)}]`;
    }
    if (value !== null && typeof value === "object") {
      const entries = Object.entries(value);
      if (!entries.length) return "{}";
      const indentation = "  ".repeat(depth + 1);
      return `{\n${indentation}${entries.map(([key, item]) =>
        `${JSON.stringify(key)}: ${formatArgumentValue(item, depth + 1)}`).join(`,\n${indentation}`)}\n${"  ".repeat(depth)}}`;
    }
    return JSON.stringify(value);
  };
  const displayArgumentValue = value => escape(formatArgumentValue(value));
  const resolvedArgumentDetails = (operatorId, operator, title, invocations) => invocations.length
    ? `<details class="profile-operator-bindings profile-operator-bindings-inline"><summary>${title}</summary>
      ${invocations.map(invocation => `<div class="ui-table-scroll" tabindex="0" role="region" aria-label="Arguments for ${escape(operatorId)}">
        <table class="ui-table"><caption class="sr-only">Arguments for ${escape(operatorId)}</caption>
          <thead><tr><th scope="col">Argument</th><th scope="col">Spec value</th><th scope="col">Resolved value</th></tr></thead>
          <tbody>${Object.entries(invocation.args || {}).map(([name, argument]) => {
            const type = argument.type.engine || argument.type.function || "";
            const engineBound = isEngineBound(argument.value, type);
            const bindValue = operator.compute.args?.[name];
            const serializedBindValue = displayArgumentValue(bindValue);
            const bindDisplay = bindValue === undefined ? "—" : isReference(bindValue)
              ? `<span class="ui-badge profile-operator-argument-value"><code class="language-json">${serializedBindValue}</code></span>`
              : `<code class="language-json">${serializedBindValue}</code>`;
            const resolvedValue = displayArgumentValue(argument.value);
            const engineBindIndicator = `<span class="profile-operator-engine-bind" tabindex="0" data-tooltip="This value will be bound only during the engine execution." aria-label="This value will be bound only during the engine execution.">${icon("engine-bind")}</span>`;
            return `<tr><th scope="row">${typedName(name, type || "—")}</th>
              <td>${bindDisplay}</td>
              <td><span class="profile-operator-resolved-value">${engineBound
    ? `<span class="ui-badge profile-operator-argument-value">${engineBindIndicator}<code class="language-json">${resolvedValue}</code></span>`
    : `<code class="language-json">${resolvedValue}</code>`}</span></td></tr>`;
          }).join("")}</tbody>
        </table></div>`).join("")}</details>` : "";
  return `<div class="profile-operator-list">${operators.map(([id, operator]) => {
    const functionId = operator.compute.function;
    const fn = config.functions[functionId] || {};
    const computeInvocations = invocations.filter(invocation =>
      invocation.profile === profileId && invocation.operator_id === id && invocation.phase === "compute"
      && Object.keys(invocation.args).length);
    const hasMerge = Boolean(operator.merge);
    const operatorName = operatorLabel(id, operator);
    return `<article id="${escape(idPrefix)}-${escape(profileId)}-${escape(id)}" class="profile-operator" data-profile-operator="${escape(id)}" data-operator-kind="${escape(operator.kind)}">
      <header class="profile-operator-header">
        <div class="profile-operator-identity"><h4>${escape(operatorName)}</h4></div>
        ${hasMerge ? `<span class="profile-operator-merge-indicator" title="The resulting fragment produced from a foreign profile needs to be merged into this profile's dataset." aria-label="The resulting fragment produced from a foreign profile needs to be merged into this profile's dataset.">${kindIcon("merge", "profile-operator-icon")}</span>` : ""}
      </header>
      <dl class="profile-operator-contract">
        <div><dt>${icon("input", "profile-operator-contract-icon")}Input features</dt><dd>${featureList(operatorInputs(operator))}</dd></div>
      </dl>
      ${operator.kind === "escape" ? '<div class="profile-operator-note">External effects are uncontrolled. Declared inputs and outputs express logical dependencies only; escape outputs are not materialized as dataframe columns.</div>' : ""}
      <div class="profile-operator-compute">
        <div class="profile-operator-function">
          ${icon("functions", "profile-operator-function-icon")}
          <a href="${href("functions", `function-${functionId}`)}">${escape(fn.name || functionId)}</a>
        </div>
        ${resolvedArgumentDetails(id, operator, "Arguments", computeInvocations)}
      </div>
      <dl class="profile-operator-contract profile-operator-output">
        <div><dt>${icon("output", "profile-operator-contract-icon")}Output features${operator.kind === "escape" ? " (logical)" : ""}</dt><dd>${featureList(operator.interface.outputs)}</dd></div>
      </dl>
    </article>`;
  }).join("")}</div>`;
}

function profileCards(config, invocations) {
  return profiles(config).map(({ id, profile }) => {
    const columns = schemaColumns(config, profile);
    const grain = profileGrain(config, profile.grain);
    const operators = Object.entries(profile.assembly);
    return `<article id="profile-${escape(id)}" data-context-item>
      <div hidden>
        <h2>${escape(label(id, profile))}</h2>
        ${profile.description ? `<p data-profile-description>${escape(profile.description)}</p>` : ""}
      </div>
      <section aria-label="Profile details">
        <div class="space-y-6">
          <div class="profile-detail-grain">${subheading("Grain", "grain")}
            <p class="mt-2 text-sm leading-6 text-slate-400">A profile is identified by its grain.</p>
            ${profileGrainHierarchies(config, profile.grain)}
          </div>
          ${profile.scope || profile.order?.length ? `<div class="grid gap-6 ${profile.scope && profile.order?.length ? "md:grid-cols-2" : ""}" data-profile-context>
          ${profile.scope ? `<div class="min-w-0">${subheading("Scope", "scope")}<blockquote class="profile-scope-quote">${description(profile.scope)}</blockquote></div>` : ""}
          ${profile.order?.length ? `<div class="min-w-0">${subheading("Logical order", "order")}<p class="mt-2 text-xs text-slate-500">Not a physical row-order guarantee.</p>${chips(profile.order.map(key => {
            const dimensionId = key.dimension;
            const dimension = config.dimensions[dimensionId];
            const resolution = dimension?.resolutions[key.resolution];
            return `${dimension?.name || dimensionId} · ${resolution?.key || key.resolution} ${key.direction}`;
          }))}</div>` : ""}</div>` : ""}
          <div>${subheading("Produced schema", "schema")}<div class="ui-table-scroll profile-schema-scroll" tabindex="0" role="region" aria-label="${escape(label(id, profile))} produced schema">
        <table data-dataset-schema="${escape(id)}" class="ui-table profile-schema-table">
          <caption class="sr-only">Produced schema for ${escape(label(id, profile))}: declared column types and units; no sample records.</caption>
          <colgroup><col class="profile-schema-name-col"><col class="profile-schema-role-col"><col class="profile-schema-unit-col"><col class="profile-schema-operator-col"></colgroup>
          <thead><tr>${["Column", "Role", "Unit", "Producing operator"].map(title => `<th scope="col">${title}</th>`).join("")}</tr></thead>
          <tbody>${columns.map(column => `<tr data-schema-column="${escape(column.id)}">
            <th scope="row">${typedName(column.id, column.type)}</th>
            <td>${badge(column.role, { dimension: "blue", teal: "green", amber: "amber", escape: "violet" }[column.color])}</td>
            <td class="profile-schema-unit">${escape(column.unit || "—")}</td>
            <td>${column.operators.length ? column.operators.map(operator => `<code class="profile-schema-operator">${escape(operator)}</code>`).join("") : '<span class="text-slate-500">None declared</span>'}</td>
          </tr>`).join("")}</tbody>
        </table></div></div>
          ${operators.length ? `<div>${subheading("Assembly", "assembly")}${profileOperatorCards(config, id, profile, operators, invocations)}</div>` : ""}
        </div></section></article>`;
  }).join("");
}

function functionMetadata(fn) {
  const returns = fn.return_type || fn.returns || fn.doc?.returns;
  const errors = fn.doc?.raises || [];
  if (!returns && !errors.length) return "";

  return `<div class="function-metadata-grid">
    ${returns ? `<section class="function-metadata-entry" aria-label="Returns">
      ${subheading("Returns", "return-arrow")}
      <div class="function-metadata-card function-detail-box">
        ${fn.return_type || fn.returns ? `<p class="function-return-type">${escape(fn.return_type || fn.returns)}</p>` : ""}
        ${fn.doc?.returns ? `<p class="function-metadata-description">${escape(fn.doc.returns)}</p>` : ""}
      </div>
    </section>` : ""}
    ${errors.length ? `<section class="function-metadata-entry" aria-label="Error handling">
      ${subheading("Error handling", "errors")}
      <div class="function-metadata-card function-detail-box">
        <ul>${errors.map(error => `<li><span class="function-error-type">${escape(error.type || "Error")}</span>${error.description ? `<p class="function-metadata-description">${escape(error.description)}</p>` : ""}</li>`).join("")}</ul>
      </div>
    </section>` : ""}
  </div>`;
}

function functionSource(fn) {
  if (!fn.entrypoint && !fn.signature_validation_disabled) return "";
  const [modulePath, ...qualifiedName] = (fn.entrypoint || "").split(":");
  const packageName = modulePath.split(".")[0];
  const fields = fn.entrypoint ? [
    ["Origin", "source-origin", {
      project: "Project source code",
      third_party: fn.source_distribution ? `Third-party (${fn.source_distribution})` : "Third-party",
    }[fn.source_origin] || "Unknown"],
    ["Package", "source-package", packageName || "—"],
    ["Module", "source-module", modulePath || "—"],
    ["Function", "functions", qualifiedName.join(":") || "—"],
  ] : [];
  return `<section class="function-source" aria-label="Source">
    ${subheading("Source", "source")}
    <div class="function-detail-box function-source-card">
      ${fields.length ? `<dl>${fields.map(([name, iconKey, value]) => `<div><dt>${icon(iconKey, "function-source-icon")}<span>${name}</span></dt><dd><code>${escape(value)}</code></dd></div>`).join("")}</dl>` : ""}
      ${fn.signature_validation_disabled ? `<div class="mt-2">${badge("Python signature validation disabled", "amber")}</div>` : ""}
    </div>
  </section>`;
}

function functionUsage(functionId, config) {
  const usages = profiles(config).flatMap(({ id, profile }) => {
    const operators = Object.entries(profile.assembly).filter(([, operator]) =>
      operator.compute.function === functionId || operator.merge?.function === functionId);
    return operators.length ? [{ id, profile, operators }] : [];
  });

  return `<section class="function-usage" aria-label="Function usage">
    ${subheading("Used by operators", "operators")}
    ${usages.length ? `<ul class="function-usage-list">${usages.map(({ id, profile, operators }) =>
      `<li class="function-usage-item function-detail-box">
        <a class="function-usage-profile" href="${href("profiles", `profile-${id}`)}">${escape(label(id, profile))}</a>
        <ul>${operators.map(([operatorId, operator]) =>
          `<li><a class="function-usage-feature" href="${href("profiles", `operator-${id}-${operatorId}`)}">${escape(operatorLabel(operatorId, operator))}</a></li>`).join("")}</ul>
      </li>`).join("")}</ul>` : '<p class="function-usage-empty">Not used by any operator.</p>'}
  </section>`;
}

function functionCards(data) {
  return Object.entries(data.catalogs.function_groups).filter(([, items]) => Object.keys(items).length).map(([category, items]) =>
    `<div id="functions-${escape(category)}" data-function-group="${escape(category)}" class="mb-20 scroll-mt-24"><div class="space-y-10">
      ${Object.entries(items).map(([id, fn]) => `<article id="function-${escape(id)}" data-context-item class="function-detail">
        <h3 class="function-detail-title">${icon("functions", "function-detail-icon")}<span>${escape(label(id, fn))}</span></h3>
        <p data-function-description class="mt-4 text-base leading-7 text-slate-300">${escape(fn.description || "No description provided.")}</p>
        ${fn.doc?.body?.trim() ? `<div class="function-description">${fn.doc.body.trim().split(/\r?\n[ \t]*\r?\n/).map(paragraph => `<p>${escape(paragraph)}</p>`).join("")}</div>` : ""}
        ${(fn.doc?.examples || []).map((example, index) => `<section class="function-example">${subheading(index ? `Example ${index + 1}` : "Example")}
          <div class="mt-3">${badge("Python")}</div>
          <pre class="function-detail-box mt-3 min-h-40 overflow-x-auto p-5 font-mono text-xs leading-6 text-slate-300"><code class="language-python">${escape(example)}</code></pre></section>`).join("")}
        <div class="function-origin-grid">
          ${functionSource(fn)}
        </div>
        ${functionUsage(id, data.catalogs.configuration)}
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
        ${functionMetadata(fn)}
      </article>`).join("")}</div></div>`).join("");
}

export function stageCards(data) {
  return data.stages.map(stage => `<section id="stage-${stage.stage}" data-context-item>
    <div class="mb-3 flex items-center gap-3"><h2 class="rounded-lg bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-300">Stage ${stage.stage}</h2>
      <span class="font-mono text-[10px] uppercase tracking-wider text-slate-500">${stage.steps.length} invocation${stage.steps.length === 1 ? "" : "s"}</span></div>
    <div class="grid grid-cols-1 gap-10">${stage.steps.map(step => `<div>
      <h3 class="mb-2 break-words font-display text-lg font-semibold text-white">${escape(step.title)}</h3><article data-invocation-id="${escape(step.invocation_id)}" data-phase="${escape(step.phase)}">
        <div class="mb-3 flex flex-wrap items-center gap-2">${badge(step.phase === "merge" ? "Merge phase" : "Compute phase", step.phase === "merge" ? "amber" : "neutral")}
          <span class="font-mono text-xs text-slate-500">Operator: ${escape(step.operator_id)}</span></div>
        <dl class="grid overflow-hidden rounded-lg border border-slate-800 bg-slate-950/55 font-mono text-xs md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_10rem]">
          ${[["Operator kind", step.operator_kind, "text-amber-200"], ["Function", step.function_label, "text-white"],
            [step.uncontrolled ? "Declared logical outputs" : "Profile feature output", step.feature || "None", "text-cyan-200"],
            [step.uncontrolled ? "Python return (ignored)" : "Returns", step.returns.type.engine || "—", "text-lime-300"]].map(([title, value, color]) => `<div class="min-w-0 border-b border-slate-800 p-3 md:border-r">
              <dt class="mb-1 uppercase tracking-wider text-slate-500">${title}</dt><dd class="break-all ${color}">${title.toLowerCase().includes("return") ? dataTypeLabel(value) : escape(value)}</dd></div>`).join("")}
          <div class="min-w-0 p-3 md:col-span-4"><dt class="mb-1 uppercase tracking-wider text-slate-500">Depends on invocations</dt>
            <dd class="flex flex-wrap gap-1.5">${step.depends_on_invocations.map(dep => `<span class="rounded-md bg-slate-950/70 px-2 py-1 text-slate-300">${escape(dep.function)}</span>`).join("") || '<span class="text-slate-400">No invocation dependencies</span>'}</dd></div>
        </dl>
        ${step.phase === "merge" ? `<dl class="mt-3 grid gap-2 rounded-lg border border-amber-900/50 bg-amber-950/15 p-3 font-mono text-xs sm:grid-cols-3">
          ${[["Merge dataset", step.merge_dataset], ["Fragment source", step.fragment_source], ["Merge keys", step.merge_keys]].map(([title, value]) =>
            `<div class="min-w-0"><dt class="mb-1 uppercase tracking-wider text-slate-500">${title}</dt><dd class="break-all text-amber-100">${display(value)}</dd></div>`).join("")}
        </dl>` : ""}
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
  const invocations = (data.stages || []).flatMap(stage => stage.steps);
  const renderers = { features: () => featureCards(config, invocations), profiles: () => profileCards(config, invocations),
    dimensions: () => dimensionCards(config),
    functions: () => functionCards(data), stages: () => stageCards(data) };
  const title = view[0].toUpperCase() + view.slice(1);
  const descriptions = {
    functions: "Browse the function catalog, argument types, return signatures, and source entrypoints.",
    dimensions: "Inspect dimension resolutions, dataframe keys, and their parent relationships.",
    features: "",
    profiles: "A profile defines computational operators required to assemble a dataset at a specific grain.",
  };
  return {
    context: catalogContext(data, view),
    content: page(`<section id="${view}" class="mb-16">
      ${view === "stages" ? '<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Execution plan</p>' : ""}
      ${view === "dimensions" ? '<p data-dimension-label class="dimension-detail-label" hidden>Dimension</p>' : ""}
      ${heading(title, descriptions[view] ?? null, view, view === "features" ? data.catalogs.summary.feature_count : null)}
      ${catalogOverview(data, view)}<div class="space-y-8">${renderers[view]()}</div></section>`),
  };
}
