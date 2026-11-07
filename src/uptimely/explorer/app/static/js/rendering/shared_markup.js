export const KINDS = {
  read: { icon: "database", label: "Read" },
  conform: { icon: "shuffle", label: "Conform" },
  expand: { icon: "expand", label: "Expand" },
  collapse: { icon: "combine", label: "Collapse" },
  vectorize: { icon: "table-properties", label: "Vectorize" },
  merge: { icon: "git-merge", label: "Merge" },
  write: { icon: "send", label: "Write" },
  escape: { icon: "arrow-up-right", label: "Escape" },
};

const ICONS = {
  home: "house", menu: "menu", "collapse-navigation": "panel-left-close",
  "expand-navigation": "panel-left-open", spec: "book-open", plan: "list-tree",
  execution: "play", info: "info", logs: "scroll-text", preview: "table-properties",
  overview: "layout-grid", features: "sigma",
  profiles: "layers-2", datasets: "table-2",
  dimensions: "axis-3d", resolutions: "scan-square", functions: "square-function",
  grain: "rows-3", scope: "filter", order: "list-ordered",
  schema: "table-2", assembly: "blocks", key: "key-round", "data-type": "braces",
  input: "arrow-right-to-line", output: "arrow-right-from-line", "engine-bind": "circle-play",
  "return-arrow": "arrow-right",
  intermediate: "workflow", dependencies: "git-branch",
  invocations: "square-function", "feature-lineage": "diagram-flow-horizontal", "invocation-lineage": "layout-arrow-right",
  "data-lineage": "monitor-play", stages: "list-ordered", reset: "scan-search",
  "zoom-in": "zoom-in", "zoom-out": "zoom-out",
  "view-2d": "square", "view-3d": "box",
};

const TYPE_ICONS = {
  float: "hash", integer: "hash", numeric: "hash", string: "case-sensitive",
  datetime: "calendar-clock", date: "calendar", boolean: "toggle-left", object: "braces", array: "brackets",
  table: "table-2",
};

export function escape(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export function dataTypeIconName(type) {
  const value = String(type ?? "").trim().toLowerCase().split(".").pop();
  const base = value.split(/[\[({<]/, 1)[0].trim();
  if (!base || ["unspecified", "unknown", "n/a", "none", "—"].includes(base)) return null;

  if (/^(?:u?int|integer|byte|short|long)\d*$/.test(base)) return TYPE_ICONS.integer;
  if (/^(?:float|double|decimal|numeric|number|real)\d*$/.test(base)) return TYPE_ICONS.float;
  if (/^(?:str|string|text|categorical|category|enum|char|varchar)$/.test(base)) return TYPE_ICONS.string;
  if (/^(?:bool|boolean)$/.test(base)) return TYPE_ICONS.boolean;
  if (/^(?:datetime|timestamp|duration|time)\d*$/.test(base)) return TYPE_ICONS.datetime;
  if (/^date\d*$/.test(base)) return TYPE_ICONS.date;
  if (/^(?:array|list|sequence|tuple|set|iterable)$/.test(base)) return TYPE_ICONS.array;
  if (/^(?:object|dict|map|struct|json)$/.test(base)) return TYPE_ICONS.object;
  if (/^(?:dataframe|data frame|series|table|record)$/.test(base)) return TYPE_ICONS.table;
  return "braces";
}

export function dataTypeIcon(type, className) {
  const lucideIcon = dataTypeIconName(type);
  return lucideIcon
    ? `<i data-lucide="${lucideIcon}" class="${className}" data-type="${escape(type)}" aria-hidden="true"></i>`
    : "";
}

export function dataTypeLabel(type, className = "") {
  const value = type || "unspecified";
  return `<span class="data-type-label${className ? ` ${className}` : ""}">
    ${dataTypeIcon(value, "data-type-label-icon")}<span class="data-type-label-text">${escape(value)}</span>
  </span>`;
}

export function typedName(name, type) {
  const value = type || "unspecified";
  return `<span class="typed-name" title="${escape(value)}" aria-label="${escape(`${name} (${value})`)}">${dataTypeIcon(value, "data-type-label-icon") || icon("data-type", "data-type-label-icon")}<span>${escape(name)}</span></span>`;
}

export function display(value) {
  return escape(value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : value);
}

export function icon(key, className = "nav-icon") {
  return `<i class="site-icon icon--${escape(key)} ${className}" data-lucide="${ICONS[key] || "braces"}" aria-hidden="true"></i>`;
}

export function kindIcon(kind, className = "nav-icon") {
  const label = KINDS[kind]?.label || kind || "Unspecified";
  return `<i class="site-icon icon--functions ${className}" data-lucide="${KINDS[kind]?.icon || "braces"}" title="Function kind: ${escape(label)}" aria-hidden="true"></i>`;
}

export function href(view, target = "") {
  return `?view=${encodeURIComponent(view)}${target ? `#${encodeURIComponent(target)}` : ""}`;
}

export function heading(title, description = null, key = title.toLowerCase(), count = null) {
  return `<header class="mb-8 border-b border-slate-800 pb-6">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="title-with-icon font-display text-3xl font-semibold tracking-tight text-white">${icon(key, "title-icon")}<span>${escape(title)}</span></h1>
      ${count === null ? "" : `<span data-section-count class="ui-badge">${escape(count)} ${escape(title.toLowerCase())}</span>`}
    </div>
    ${description === null ? "" : `<p data-section-description class="mt-3 max-w-3xl text-sm leading-6 text-slate-400"${description ? "" : " hidden"}>${escape(description)}</p>`}
  </header>`;
}

export function badge(label, tone = "neutral") {
  return `<span class="ui-badge ui-badge--${escape(tone)}">${escape(label)}</span>`;
}

export function statistic(label, value) {
  return `<div class="ui-panel" data-stat="${escape(label)}">
    <span class="text-xs text-slate-400">${escape(label)}</span>
    <p class="mt-4 font-display text-3xl font-semibold text-white" data-value="${escape(value ?? 0)}">${escape(value ?? 0)}</p>
  </div>`;
}

export function distribution(title, counts, {
  total = null, note = null, typeLabels = false, iconLabels = false, kindLabels = false,
  returnTypeLabels = false, tooltip = null,
} = {}) {
  const maximum = Math.max(0, ...counts.map(([, value]) => Number(value)));
  return `<section class="ui-panel ui-chart">
    <div class="ui-panel-heading"><div class="ui-chart-title"><h3>${escape(title)}</h3>
      ${tooltip ? `<span class="ui-chart-tooltip" tabindex="0" data-tooltip="${escape(tooltip)}" aria-label="${escape(tooltip)}">${icon("info", "ui-chart-tooltip-icon")}</span>` : ""}
      </div>
      ${total === null ? "" : `<span class="ui-panel-meta">total ${escape(total)}</span>`}</div>
    ${note ? `<p class="ui-panel-description">${escape(note)}</p>` : ""}
    <div class="space-y-4">${counts.map(([label, value, target]) => {
      const tag = target ? "a" : "div";
      return `<${tag}${target ? ` href="${escape(target)}"` : ""} class="ui-chart-row" data-category="${escape(label)}" data-count="${escape(value)}">
        <span class="${iconLabels || kindLabels || returnTypeLabels ? "inline-flex items-center gap-2 break-words text-slate-400" : "break-words text-slate-400"}">${kindLabels ? kindIcon(label, "h-4 w-4 shrink-0") : iconLabels ? icon(label, "h-4 w-4 shrink-0") : returnTypeLabels ? icon("return-arrow", "h-4 w-4 shrink-0") : ""}${returnTypeLabels ? `<span class="data-type-label-text">${escape(label)}</span>` : typeLabels ? dataTypeLabel(label) : escape(label)}</span>
        <div class="h-3 overflow-hidden rounded-full bg-slate-800" aria-hidden="true"><div class="h-full rounded-full ${label === "merge" ? "bg-amber-400" : label === "escape" ? "bg-violet-400" : "bg-cyan-400"}" style="width:${maximum ? Number(value) / maximum * 100 : 0}%"></div></div>
        <span class="text-right font-mono text-xs text-white">${escape(value)}</span>
      </${tag}>`;
    }).join("") || '<p class="text-sm text-slate-400">No categories to display.</p>'}</div>
  </section>`;
}

export function page(content) {
  return `<div class="model-grid pointer-events-none fixed inset-0 -z-0 opacity-30"></div>
    <div class="relative z-10 mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-10"><main>${content}</main></div>`;
}

export function contextHeader(title, key, id, label = title.toLowerCase()) {
  const tag = ["catalog-context", "preview-context"].includes(id) ? "h2" : "h1";
  return `<div class="context-header">
    <div class="context-heading site-nav-heading">
    <${tag} class="title-with-icon" title="${escape(title)}">${icon(key)}<span>${escape(title)}</span></${tag}>
    <button class="nav-label-toggle context-label-toggle" type="button" aria-label="Collapse ${escape(label)} context"
      aria-pressed="false" aria-controls="${id}" title="Collapse ${escape(label)} context">${icon("collapse-navigation")}${icon("expand-navigation")}</button>
    <button class="ui-button context-sheet-close" type="button" aria-label="Close ${escape(label)} menu">Close</button>
    </div></div>`;
}

export function contextGroup(title, items) {
  return `<div class="context-link-group">
  <p class="context-group-label"><span>${escape(title)}</span><span class="context-link-count">${items.length}</span></p>${items.join("")}</div>`;
}

export function contextLink(target, label, key, count = null, kind = null, type = null) {
  return `<a href="#${encodeURIComponent(target)}">
    ${type !== null ? `<span class="context-link-icon" title="${escape(type)}">${dataTypeIcon(type, "nav-icon") || icon("data-type", "nav-icon")}</span>`
      : key || kind ? `<span class="context-link-icon">${kind ? kindIcon(kind) : icon(key)}</span>` : ""}
    <span class="context-link-label">${escape(label)}</span>
    ${type === null ? "" : `<span class="sr-only"> (${escape(type)})</span>`}
    ${count === null ? "" : `<span class="context-link-count">${escape(count)}</span>`}
  </a>`;
}

export function shell(data, view, context, content) {
  const projectName = escape(data.project.name || "Untitled analytics project");
  const contextTitle = ["lineage", "topology"].includes(view) ? "Legend & details"
    : view === "animation" ? "Animation steps" : view[0].toUpperCase() + view.slice(1);
  const projectLink = `<a class="site-product" href="${href("home")}" title="${projectName}" aria-label="${projectName}"${view === "home" ? ' aria-current="page"' : ""}><span>${projectName}</span></a>`;
  const navigationGroups = [
    ["spec", "Analytical model", [
      ["profiles", "Profiles", "profiles"],
      ["features", "Features", "features"], ["functions", "Functions", "functions"],
      ["dimensions", "Dimensions", "dimensions"],
      ["lineage", "Lineage", "feature-lineage"],
    ]],
    ["plan", "Execution plan", [
      ["plan", "Overview", "overview"], ["topology", "Topology", "invocation-lineage"],
      ["stages", "Stages", "stages"],
    ]],
    ["execution", "Run results", [
      ["info", "Info", "info"], ["logs", "Log", "logs"],
      ["preview", "Preview", "preview"],
      ["animation", "Animation", "data-lineage"],
    ]],
  ];
  return `<header class="site-topbar" aria-label="Project context">
      <button class="mobile-nav-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="explorer-navigation">${icon("menu")}</button>${projectLink}
    </header>
    ${context ? `<section class="mobile-context-bar" aria-label="Page controls">
      <button class="mobile-context-toggle ui-button" type="button" aria-expanded="false">
        <span>${escape(contextTitle)}</span><i data-lucide="chevron-down" aria-hidden="true"></i>
      </button><div class="mobile-primary-controls"></div>
    </section><button class="context-backdrop" type="button" aria-label="Close page controls" tabindex="-1"></button>` : ""}
    <div class="site-menus" id="explorer-menus">
    <nav class="site-nav" id="explorer-navigation" aria-label="Explorer pages">
      <div class="site-nav-context"><div class="site-nav-heading">${projectLink}
        <button class="nav-label-toggle" type="button" aria-label="Hide navigation labels" aria-pressed="false" aria-controls="explorer-navigation" title="Hide navigation labels">${icon("collapse-navigation")}${icon("expand-navigation")}</button>
      </div></div>
      <div class="site-nav-pages">${navigationGroups.map(([key, title, sections]) => `
        <section class="site-nav-group" aria-labelledby="nav-group-${key}">
        <h2 class="site-nav-group-title" id="nav-group-${key}">${title}</h2>
        <div class="site-subnav" role="group" aria-label="${title} sections">${sections.map(([route, label, glyph]) => `
          <a aria-label="${label}" title="${label}" href="${href(route)}"${view === route ? ' aria-current="page"' : ""}>${icon(glyph)}<span>${label}</span></a>`).join("")}</div></section>`).join("")}</div>
      <span id="scope-badge" class="build-badge${data.scope.is_scoped ? " build-badge-partial" : ""}"
        title="Spec: complete model. Plan and execution: ${escape(data.scope.label)}"
        aria-label="Build coverage: ${data.scope.is_scoped ? "Partial" : "Full"} build. Spec: complete model. Plan and execution: ${escape(data.scope.label)}">${data.scope.is_scoped ? "Partial" : "Full"} build</span>
    </nav>
    ${context}</div><div class="site-content" id="content">${content}</div>`;
}

export function miniGraphic(kind) {
  const key = "#475569", feature = "#22d3ee", foreign = "#a78bfa", result = "#fbbf24";
  const table = (x, y, rows) => rows.map((row, i) => row.map((fill, j) =>
    `<rect x="${x + j * 17}" y="${y + i * 10}" width="14" height="7" rx="2" fill="${fill}"/>`).join("")).join("");
  const repeated = row => [row, row, row];
  const arrow = '<path d="M62 22h14m-4.5-4.5 4.5 4.5-4.5 4.5" stroke="#64748b" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
  const external = '<ellipse cx="30" cy="11" rx="15" ry="5" fill="none" stroke="#475569" stroke-width="1.5"/><path d="M15 11v21c0 2.8 6.7 5 15 5s15-2.2 15-5V11M15 22c0 2.8 6.7 5 15 5s15-2.2 15-5" fill="none" stroke="#475569" stroke-width="1.5"/>';
  const input = kind === "read" ? external : kind === "conform"
    ? table(14, 2, [[`${key}66`, `${foreign}55`], [key, foreign], [key, foreign], [`${key}66`, `${foreign}55`]])
    : table(14, kind === "expand" ? 19 : 7,
      kind === "expand" ? [[key, foreign]] : repeated(kind === "collapse" ? [key, key, feature] : kind === "write" ? [key, result] : [key, feature]));
  const output = kind === "write"
    ? '<g transform="translate(97 10)" fill="none" stroke="#22d3ee" stroke-width="1.5"><path d="m22 2-7 20-4-9-9-4ZM22 2 11 13"/></g>'
    : kind === "escape"
      ? '<rect x="96" y="9" width="26" height="26" rx="7" fill="none" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="3 3"/><path d="m104 27 10-10m-6 0h6v6" fill="none" stroke="#a78bfa" stroke-width="1.5"/>'
      : kind === "conform" ? table(98, 12, [[key, foreign], [key, foreign]])
        : table(kind === "collapse" ? 98 : 94, kind === "collapse" ? 19 : 7,
          kind === "collapse" ? [[key, result]] : repeated(kind === "vectorize" ? [key, feature, result] : kind === "expand" ? [key, key, foreign] : kind === "read" ? [key, feature, feature] : [key, feature]));
  return `<svg viewBox="0 0 150 44" class="h-11 w-auto" aria-hidden="true" focusable="false">${input}${arrow}${output}</svg>`;
}
