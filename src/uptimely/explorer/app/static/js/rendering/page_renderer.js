import { contextHeader, contextToggle, escape, heading, href, icon, page } from "./shared_markup.js";

export function dashboard(data) {
  const summary = data.catalogs.summary;
  return `<main class="dashboard">
    <header class="dashboard-hero"><div>
      <p class="eyebrow">Project explorer</p>
      <h1 class="title-with-icon">${icon("home", "title-icon")}<span>${escape(data.project.name || "Untitled analytics project")}</span></h1>
      <p class="dashboard-intro">From declared data to a dependency-aware plan.
        Explore what this analytics project defines, how its plan is compiled,
        and how its data flows through execution.</p>
      <span class="dashboard-version">Spec ${escape(data.project.spec_version)}</span>
    </div>
    <svg class="dashboard-art" viewBox="0 0 420 280" fill="none" aria-hidden="true" focusable="false">
      <defs><linearGradient id="journey-gradient" x1="80" y1="60" x2="340" y2="230" gradientUnits="userSpaceOnUse">
        <stop stop-color="#67e8f9"/><stop offset=".5" stop-color="#fcd34d"/><stop offset="1" stop-color="#e879f9"/></linearGradient></defs>
      <circle cx="210" cy="140" r="118" stroke="#334155" stroke-dasharray="3 9"/>
      <circle cx="210" cy="140" r="82" stroke="#1e293b"/>
      <path d="M88 72H190Q210 72 210 92V188Q210 208 230 208H332" stroke="url(#journey-gradient)" stroke-width="2"/>
      <path d="M88 72V208H156M264 72H332V208" stroke="#334155" stroke-dasharray="4 6"/>
      <rect x="48" y="32" width="80" height="80" rx="20" fill="#0f172a" stroke="#67e8f9"/>
      <path d="M72 53H104V91H72V53ZM79 64H97M79 72H97M79 80H89" stroke="#67e8f9" stroke-width="2"/>
      <rect x="170" y="100" width="80" height="80" rx="20" fill="#0f172a" stroke="#fcd34d"/>
      <path d="M196 124L224 140L196 156M196 124V156" stroke="#fcd34d" stroke-width="2"/>
      <circle cx="196" cy="124" r="5" fill="#0f172a" stroke="#fcd34d" stroke-width="2"/>
      <circle cx="224" cy="140" r="5" fill="#0f172a" stroke="#fcd34d" stroke-width="2"/>
      <circle cx="196" cy="156" r="5" fill="#0f172a" stroke="#fcd34d" stroke-width="2"/>
      <rect x="292" y="168" width="80" height="80" rx="20" fill="#0f172a" stroke="#e879f9"/>
      <path d="M314 193H350M314 208H338M314 223H326" stroke="#e879f9" stroke-width="3" stroke-linecap="round"/>
      <circle cx="156" cy="208" r="4" fill="#67e8f9"/><circle cx="264" cy="72" r="4" fill="#e879f9"/>
    </svg></header>
    <dl class="dashboard-metrics" aria-label="Project counts">${[
      ["Profiles", summary.profile_count],
      ["Features", summary.feature_count], ["Functions", summary.function_count],
      ["Invocations", data.plan.invocation_count], ["Stages", data.plan.stage_count],
    ].map(([label, count]) => `<div data-stat="${label}" data-value="${count}"><dt>${label}</dt><dd>${count}</dd></div>`).join("")}</dl>
    <section aria-labelledby="journey-heading"><p class="eyebrow">Three perspectives. One project.</p>
      <h2 class="dashboard-section-title" id="journey-heading">Follow the analytics journey</h2>
      <p class="dashboard-section-intro">Start with the declarations, inspect the compiled plan, then explore execution.</p>
      <ol class="spec-journey" aria-label="Spec journey">${[
        ["spec", "01", "Spec", "The source of truth. Browse profiles, features, dimensions, and the functions bound to them.", "spec", "Explore spec"],
        ["plan", "02", "Plan", "The path to execution. Inspect compiled operations, argument bindings, and dependency-ordered stages with potential parallelism.", "plan", "Inspect the plan"],
        ["execution", "03", "Execution", "Follow color-coded processing tables and the dependencies connecting them.", "animation", "Explore execution"],
      ].map(([key, number, title, description, view, action]) => `<li class="journey-step ${key} icon--${key}">
        <div class="journey-step-header"><span class="journey-icon">${icon(key)}</span><span class="journey-number" aria-hidden="true">${number}</span></div>
        <h3>${title}</h3><p>${description}</p><a href="${href(view)}">${action}<i data-lucide="arrow-right" aria-hidden="true"></i></a></li>`).join("")}</ol>
    </section>
    <p class="dashboard-note">A view of your declared spec, not a live execution monitor.
      Counts describe the spec and its compiled plan; building this website does not run analytical operations.</p>
  </main>`;
}

function overviewChart(title, counts, total, suffix = "") {
  const maximum = Math.max(0, ...counts.map(([, value]) => value));
  return `<div class="rounded-2xl border border-slate-800 bg-slate-900/75 p-5">
    <div class="mb-5 flex items-baseline justify-between gap-4"><h2 class="font-display text-lg font-semibold text-white">${title}</h2>
      <div class="flex gap-3 font-mono text-[10px] uppercase tracking-wider text-slate-500"><span>total ${total}</span>${suffix}</div></div>
    <div class="space-y-4">${counts.map(([name, value]) => `<div class="grid grid-cols-[5.5rem_minmax(0,1fr)_2rem] items-center gap-3" data-category="${escape(name)}" data-count="${value}">
      <span class="font-mono text-xs text-slate-400">${escape(name)}</span><div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full ${name === "escape" ? "bg-violet-400" : "bg-cyan-400"}" style="width:${maximum ? value / maximum * 100 : 0}%"></div></div>
      <span class="text-right font-mono text-xs text-white">${value}</span></div>`).join("")}</div></div>`;
}

export function specOverview(data) {
  const config = data.catalogs.configuration, summary = data.catalogs.summary;
  const source = config.source || {};
  return page(heading("Overview", "A summary of the profiles, features, and functions declared in this spec.") + `
    <div class="relative mb-8 overflow-hidden rounded-3xl border border-cyan-900/60 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/50 p-6 shadow-xl shadow-cyan-950/10 sm:p-8"
      data-source-name="${escape(source.name || "manual")}" data-generated="${Boolean(source.generated)}">
      <div class="pointer-events-none absolute -right-12 -top-20 h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl" aria-hidden="true"></div>
      <div class="relative"><p class="font-mono text-[10px] uppercase tracking-[.2em] text-cyan-300/70">Spec profile</p>
        <h2 class="mt-3 break-words font-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">${escape(config.name || data.project.name || "Untitled spec")}</h2>
        <div class="mt-6 flex flex-wrap gap-3">
          <div class="min-w-40 rounded-xl border border-slate-700/80 bg-slate-950/40 px-4 py-3"><p class="font-mono text-[10px] uppercase tracking-[.16em] text-slate-500">Source</p><p class="mt-1.5 break-all font-mono text-sm font-medium text-cyan-200">${escape(source.name || "manual")}</p></div>
          <div class="min-w-40 rounded-xl border border-slate-700/80 bg-slate-950/40 px-4 py-3"><p class="font-mono text-[10px] uppercase tracking-[.16em] text-slate-500">Generated</p>
            <div class="mt-1.5 flex items-center gap-2"><span class="h-2 w-2 rounded-full ${source.generated ? "bg-emerald-400" : "bg-amber-300"}" aria-hidden="true"></span>
              <span class="font-mono text-sm font-medium ${source.generated ? "text-emerald-200" : "text-amber-200"}">${Boolean(source.generated)}</span>
              <span class="text-xs text-slate-400">${source.generated ? "Framework-generated" : "Hand-written"}</span></div></div>
        </div></div></div>
    <div class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">${[
      ["Profiles", summary.profile_count],
      ["Actions", summary.action_count, "functions"], ["Dimensions", summary.dimension_count],
    ].map(([title, value]) => `<div class="rounded-2xl border border-slate-800 bg-slate-900/75 p-5"><span class="font-mono text-[10px] uppercase tracking-[.15em] text-slate-500">${title}</span><p class="mt-4 font-display text-3xl font-semibold text-white">${value}</p></div>`).join("")}</div>
    <div class="mt-5 grid gap-5 lg:grid-cols-2">
      ${overviewChart("Features", ["input", "intermediate", "output"].map(key => [key, summary.feature_buckets[key] || 0]), summary.feature_count, `<span>vectorized ${summary.vectorized_feature_count ?? 0}</span>`)}
      ${overviewChart("Functions", ["read", "write", "escape", "vectorize", "collapse", "expand", "conform"].map(key => [key, summary.function_buckets[key] || 0]), summary.function_count)}
    </div>`);
}

export function planOverview(data) {
  const plan = data.plan;
  return page(`<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Plan</p>
    ${heading("Overview", "Plan compiled from the spec, ordered by dependency resolution.")}
    <section id="plan-overview" class="mb-16">
      <div class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">${[
        ["Invocations", plan.invocation_count], ["Functions", plan.function_count],
        ["Profiles", plan.profile_count], ["Features", plan.feature_count], ["Stages", plan.stage_count],
        ["Dependencies", plan.dependency_count, "invocation-lineage"], ["Max parallel invocations", plan.max_parallel_invocations, "stages"],
      ].map(([title, value, key]) => `<div class="rounded-2xl border border-slate-800 bg-slate-900/75 p-5" data-stat="${title}">
        <div class="flex items-center justify-between gap-3"><span class="font-mono text-[10px] uppercase tracking-[.15em] text-slate-500">${title}</span>${icon(key || title.toLowerCase())}</div>
        <p class="mt-4 font-display text-3xl font-semibold text-white" data-value="${value}">${value}</p></div>`).join("")}</div>
      <div class="mt-5 grid gap-5 lg:grid-cols-2">${overviewChart("Invocations", plan.function_kind_counts, plan.invocation_count)}
        <div class="rounded-2xl border border-slate-800 bg-slate-900/75 p-5">
          <div class="mb-2 flex items-baseline justify-between gap-4"><h2 class="font-display text-lg font-semibold text-white">Execution stages</h2><span class="font-mono text-[10px] uppercase tracking-wider text-slate-500">total ${plan.stage_count}</span></div>
          <p class="mb-5 text-xs leading-5 text-slate-400">Invocations in each stage can run independently. Actual parallel execution depends on the engine.</p>
          <div class="space-y-4">${data.stages.map(stage => `<div class="grid grid-cols-[5.5rem_minmax(0,1fr)_3rem] items-center gap-3" data-stage="${stage.stage}" data-count="${stage.steps.length}">
            <span class="font-mono text-xs text-slate-400">Stage ${stage.stage}</span><div class="h-2 overflow-hidden rounded-full bg-slate-800"><div class="h-full rounded-full bg-cyan-400" style="width:${plan.max_parallel_invocations ? stage.steps.length / plan.max_parallel_invocations * 100 : 0}%"></div></div>
            <span class="text-right font-mono text-xs text-white">${stage.steps.length}</span></div>`).join("")}</div>
        </div></div></section>`);
}

export function lineage(data, topology) {
  const title = topology ? "Topology" : "Lineage";
  const key = topology ? "invocation-lineage" : "feature-lineage";
  const panelId = topology ? "invocation-node-details" : "node-details";
  const graph = topology ? data.graphs.invocation_lineage : data.graphs.feature_lineage;
  const style = topology ? data.graphs.invocation_style : data.graphs.feature_style;
  const payload = (id, value) => `<script id="${id}" type="application/json">${JSON.stringify(value).replace(/</g, "\\u003c")}</script>`;
  return {
    context: `<aside class="site-context" id="lineage-context" aria-label="Lineage context" data-context-label="lineage">
      ${contextHeader(title, key, "lineage-context", "lineage")}
      <button class="ui-button context-close" type="button" aria-label="Close lineage context">Close</button>
      <div class="lineage-control-groups">
        <div class="lineage-buttons" role="group" aria-label="Lineage view">
          <button class="ui-button" type="button" data-dimension="2d" aria-pressed="true" aria-controls="lineage-2d">2D</button>
          <button class="ui-button" type="button" data-dimension="3d" aria-pressed="false" aria-controls="lineage-3d">3D</button>
        </div>
        <div class="lineage-buttons" role="group" aria-label="Lineage zoom"><button class="ui-button" type="button" data-zoom="1.25" aria-label="Zoom in">+</button><button class="ui-button" type="button" data-zoom="0.8" aria-label="Zoom out">-</button></div>
        <div class="lineage-buttons" role="group" aria-label="Lineage reset"><button class="ui-button" id="reset-lineage" type="button">Reset lineage</button></div>
      </div>
      <details class="panel" open><summary>Legend</summary><div class="legend" aria-label="Legend">
        ${topology ? "" : '<span class="function" id="action-legend">Action</span>'}<span class="legend-heading">Datasets</span>
        <div class="dataset-legend" id="dataset-legend"></div></div></details>
      <div class="details" id="${panelId}" role="region" aria-label="${topology ? "Invocation details" : "Selected item"}" aria-live="polite">
        <h2>${topology ? "Invocation details" : "Selected item"}</h2><div class="meta">Click a node</div>
        <div class="summary">${topology ? "Select an invocation to inspect its function kind, arguments, profile, declared features, and invocation dependencies." : "Select any feature in the lineage to see its identifier and details."}</div>
      </div></aside>`,
    content: `<main class="lineage-workspace"><div class="lineage-stage">${contextToggle("lineage-context", "Lineage")}
      <p id="lineage-error" role="alert" hidden></p>
      ${topology ? '<section id="invocation-lineage-graph">' : ""}
      <div id="lineage"><div id="lineage-2d" class="lineage-view"></div><div id="lineage-3d" class="lineage-view" hidden></div></div>
      ${topology ? "</section>" : ""}${payload("graph-data", graph)}${payload("graph-style", style)}</div></main>`,
  };
}
