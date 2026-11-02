export const KINDS = {
  read: { icon: "database", label: "Read" },
  conform: { icon: "shuffle", label: "Conform" },
  expand: { icon: "expand", label: "Expand" },
  collapse: { icon: "combine", label: "Collapse" },
  vectorize: { icon: "wand-sparkles", label: "Vectorize" },
  write: { icon: "send", label: "Write" },
  escape: { icon: "arrow-up-right", label: "Escape" },
};

const ICONS = {
  home: "house", menu: "menu", "collapse-navigation": "panel-left-close",
  "expand-navigation": "panel-left-open", spec: "book-open", plan: "list-tree",
  execution: "play", overview: "layout-dashboard", features: "sigma",
  entities: "boxes", datasets: "table", dimensions: "layers-3", functions: "braces",
  invocations: "braces", "feature-lineage": "network", "invocation-lineage": "workflow",
  "data-lineage": "database-zap", stages: "list-ordered",
};

export function escape(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export function display(value) {
  return escape(value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : value);
}

export function icon(key, className = "nav-icon") {
  return `<i class="site-icon icon--${escape(key)} ${className}" data-lucide="${ICONS[key] || "braces"}" aria-hidden="true"></i>`;
}

export function kindIcon(kind, className = "nav-icon") {
  return `<i class="site-icon icon--functions ${className}" data-lucide="${KINDS[kind]?.icon || "braces"}" aria-hidden="true"></i>`;
}

export function href(view, target = "") {
  return `?view=${encodeURIComponent(view)}${target ? `#${encodeURIComponent(target)}` : ""}`;
}

export function heading(title, description = null, key = title.toLowerCase(), count = null) {
  return `<header class="mb-8 border-b border-slate-800 pb-6">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="title-with-icon font-display text-3xl font-semibold tracking-tight text-white">${icon(key, "title-icon")}<span>${escape(title)}</span></h1>
      ${count === null ? "" : `<span data-section-count class="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 font-mono text-xs text-slate-400">${escape(count)} ${escape(title.toLowerCase())}</span>`}
    </div>
    ${description === null ? "" : `<p data-section-description class="mt-3 max-w-3xl text-sm leading-6 text-slate-400">${escape(description)}</p>`}
  </header>`;
}

export function statistic(label, value, key = label.toLowerCase()) {
  return `<div class="rounded-2xl border border-slate-800 bg-slate-900/75 p-5" data-stat="${escape(label)}">
    <div class="flex items-center justify-between gap-3"><span class="text-xs text-slate-400">${escape(label)}</span>${icon(key)}</div>
    <p class="mt-4 font-display text-3xl font-semibold text-white" data-value="${escape(value ?? 0)}">${escape(value ?? 0)}</p>
  </div>`;
}

export function distribution(title, counts) {
  const maximum = Math.max(0, ...counts.map(([, value]) => Number(value)));
  return `<div class="mt-6 rounded-2xl border border-slate-800 bg-slate-900/75 p-5">
    <h3 class="mb-5 font-display text-lg font-semibold text-white">${escape(title)}</h3>
    <div class="space-y-4">${counts.map(([label, value]) => {
      return `<div class="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_3rem] items-center gap-3" data-category="${escape(label)}" data-count="${escape(value)}">
        <span class="break-words font-mono text-xs text-slate-400">${escape(label)}</span>
        <div class="h-2 overflow-hidden rounded-full bg-slate-800" aria-hidden="true"><div class="h-full rounded-full ${label === "escape" ? "bg-violet-400" : "bg-cyan-400"}" style="width:${maximum ? Number(value) / maximum * 100 : 0}%"></div></div>
        <span class="text-right font-mono text-xs text-white">${escape(value)}</span>
      </div>`;
    }).join("") || '<p class="text-sm text-slate-400">No categories to display.</p>'}</div>
  </div>`;
}

export function page(content) {
  return `<div class="model-grid pointer-events-none fixed inset-0 -z-0 opacity-30"></div>
    <div class="relative z-10 mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-10"><main>${content}</main></div>`;
}

export function contextHeader(title, key, id, label = title.toLowerCase()) {
  const tag = id === "catalog-context" ? "h2" : "h1";
  return `<div class="context-header"><div class="context-heading site-nav-heading">
    <${tag} class="title-with-icon" title="${escape(title)}">${icon(key)}<span>${escape(title)}</span></${tag}>
    <button class="nav-label-toggle context-label-toggle" type="button" aria-label="Collapse ${escape(label)} context"
      aria-pressed="false" aria-controls="${id}" title="Collapse ${escape(label)} context">${icon("collapse-navigation")}${icon("expand-navigation")}</button>
    </div></div>`;
}

export function contextToggle(id, label) {
  return `<button class="ui-button context-toggle" type="button" aria-label="Show ${escape(label.toLowerCase())} context"
    aria-expanded="false" aria-controls="${id}">${escape(label)} controls</button>`;
}

export function contextLink(target, label, key, count = null, kind = null) {
  return `<a href="#${encodeURIComponent(target)}">
    ${key || kind ? `<span class="context-link-icon">${kind ? kindIcon(kind) : icon(key)}</span>` : ""}
    <span class="context-link-label">${escape(label)}</span>
    ${count === null ? "" : `<span class="context-link-count">${escape(count)}</span>`}
  </a>`;
}

export function shell(data, view, context, content) {
  const projectName = escape(data.project.name || "Untitled analytics project");
  const projectLink = `<a class="site-product" href="${href("home")}" title="${projectName}" aria-label="${projectName}"${view === "home" ? ' aria-current="page"' : ""}>${icon("home")}<span>${projectName}</span></a>`;
  const navigationGroups = [
    ["spec", "Spec", [
      ["spec", "Overview", "overview"], ["features", "Features", "features"],
      ["entities", "Entities", "entities"], ["datasets", "Datasets", "datasets"],
      ["dimensions", "Dimensions", "dimensions"], ["functions", "Functions", "functions"],
      ["lineage", "Lineage", "feature-lineage"],
    ]],
    ["plan", "Plan", [
      ["plan", "Overview", "overview"], ["topology", "Topology", "invocation-lineage"],
      ["stages", "Stages", "stages"],
    ]],
    ["execution", "Execution", [["animation", "Animation", "data-lineage"]]],
  ];
  return `<header class="site-topbar" aria-label="Project context">
      <button class="mobile-nav-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="explorer-navigation">${icon("menu")}</button>${projectLink}
    </header>
    <nav class="site-nav" id="explorer-navigation" aria-label="Explorer pages">
      <div class="site-nav-context"><div class="site-nav-heading">${projectLink}
        <button class="nav-label-toggle" type="button" aria-label="Hide navigation labels" aria-pressed="false" aria-controls="explorer-navigation" title="Hide navigation labels">${icon("collapse-navigation")}${icon("expand-navigation")}</button>
      </div></div>
      <div class="site-nav-pages">${navigationGroups.map(([key, title, sections]) => `
        <a aria-label="${title}" title="${title}" href="${href(sections[0][0])}">${icon(key)}<span>${title}</span></a>
        <div class="site-subnav" role="group" aria-label="${title} sections">${sections.map(([route, label, glyph]) => `
          <a aria-label="${label}" title="${label}" href="${href(route)}"${view === route ? ' aria-current="page"' : ""}>${icon(glyph)}<span>${label}</span></a>`).join("")}</div>`).join("")}</div>
      <span id="scope-badge" class="build-badge${data.scope.is_scoped ? " build-badge-partial" : ""}"
        title="Spec: complete model. Plan and execution: ${escape(data.scope.label)}"
        aria-label="Build coverage: ${data.scope.is_scoped ? "Partial" : "Full"} build. Spec: complete model. Plan and execution: ${escape(data.scope.label)}">${data.scope.is_scoped ? "Partial" : "Full"} build</span>
    </nav>
    ${context}<div class="site-content" id="content">${content}</div>`;
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
