import { contextHeader, distribution, escape, heading, href, icon, page, statistic } from "./shared_markup.js";

export function dashboard(data) {
  const summary = data.catalogs.summary;
  return `<main class="dashboard">
    <header class="dashboard-hero"><div>
      <p class="eyebrow">Project explorer</p>
      <h1><span>${escape(data.project.name || "Untitled analytics project")}</span></h1>
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
        ["spec", "01", "Analytical model", "Browse profiles, features, dimensions, and the functions bound to them.", "features", "Explore the model"],
        ["plan", "02", "Execution plan", "Inspect compiled operations, argument bindings, and dependency-ordered stages.", "plan", "Inspect the plan"],
        ["execution", "03", "Run results", "Inspect the latest saved run, its logs, and profile dataset previews.", "info", "View run results"],
      ].map(([key, number, title, description, view, operator]) => `<li class="journey-step ${key} icon--${key}">
        <div class="journey-step-header"><span class="journey-icon">${icon(key)}</span><span class="journey-number" aria-hidden="true">${number}</span></div>
        <h3>${title}</h3><p>${description}</p><a href="${href(view)}">${operator}<i data-lucide="arrow-right" aria-hidden="true"></i></a></li>`).join("")}</ol>
    </section>
    <p class="dashboard-note">Counts describe the analytical model and its compiled plan.
      Run results are saved by <code>uptimely run</code>; browsing the Explorer does not execute analytical operations.</p>
  </main>`;
}

export function planOverview(data) {
  const plan = data.plan;
  return page(`<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Execution plan</p>
    ${heading("Stats", "Plan compiled from the spec, ordered by dependency resolution.", "stats")}
    <section id="plan-overview" class="mb-16">
      <div class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">${[
        ["Invocations", plan.invocation_count], ["Functions", plan.function_count],
        ["Profiles", plan.profile_count], ["Features", plan.feature_count], ["Stages", plan.stage_count],
        ["Dependencies", plan.dependency_count], ["Max parallel invocations", plan.max_parallel_invocations],
      ].map(args => statistic(...args)).join("")}</div>
      <div class="catalog-charts lg:grid-cols-2">${distribution("Invocations by function kind", plan.function_kind_counts, { total: plan.invocation_count })}
        ${distribution("Invocations by stage", data.stages.map(stage => [`Stage ${stage.stage}`, stage.steps.length]), {
          total: plan.invocation_count,
          note: "Invocations in each stage can run independently. Actual parallel execution depends on the engine.",
        })}</div></section>`);
}

export function lineage(data, topology) {
  const title = topology ? "Topology" : "Lineage";
  const key = topology ? "invocation-lineage" : "feature-lineage";
  const panelId = topology ? "invocation-node-details" : "node-details";
  const graph = topology ? data.graphs.invocation_lineage : data.graphs.feature_lineage;
  const style = topology ? data.graphs.invocation_style : data.graphs.feature_style;
  const payload = (id, value) => `<script id="${id}" type="application/json">${JSON.stringify(value).replace(/</g, "\\u003c")}</script>`;
  return {
    context: `<aside class="site-context" id="lineage-context" aria-label="${title} context" data-context-label="${title.toLowerCase()}">
      ${contextHeader(title, key, "lineage-context", title.toLowerCase())}
      <div class="lineage-control-groups">
        <div class="lineage-buttons" role="group" aria-label="${title} view">
          <button class="ui-button" type="button" data-dimension="2d" title="Show 2D view" aria-label="Show 2D view" aria-pressed="true" aria-controls="lineage-2d">${icon("view-2d")}</button>
          <button class="ui-button" type="button" data-dimension="3d" title="Show 3D view" aria-label="Show 3D view" aria-pressed="false" aria-controls="lineage-3d">${icon("view-3d")}</button>
        </div>
        ${topology ? "" : `<button class="ui-button lineage-operator-toggle" id="show-operators" type="button" aria-label="Show operators" title="Show operators" aria-pressed="true" aria-controls="lineage">${icon("functions")}</button>`}
        <div class="lineage-buttons" role="group" aria-label="${title} viewport">
          <button class="ui-button" type="button" data-zoom="1.25" aria-label="Zoom in" title="Zoom in">${icon("zoom-in")}</button>
          <button class="ui-button" type="button" data-zoom="0.8" aria-label="Zoom out" title="Zoom out">${icon("zoom-out")}</button>
          <button class="ui-button lineage-reset" id="reset-lineage" type="button" aria-label="Reset view" title="Reset view" aria-controls="lineage">${icon("reset")}</button>
        </div>
      </div>
      <details class="panel" open><summary>Legend</summary><div class="legend" aria-label="Legend">
        ${topology ? "" : '<span class="function" id="operator-legend">Operator</span>'}<span class="legend-heading">Profiles</span>
        <div class="dataset-legend" id="dataset-legend"></div></div></details>
      <div class="details" id="${panelId}" role="region" aria-label="${topology ? "Invocation details" : "Selected item"}" aria-live="polite">
        <h2>${topology ? "Invocation details" : "Selected item"}</h2><div class="meta">Click a node</div>
        <div class="summary">${topology ? "Select an invocation to inspect its function kind, arguments, profile, declared features, and invocation dependencies." : "Select a feature or visible operator to see its identifier and details."}</div>
      </div></aside>`,
    content: `<main class="lineage-workspace"><div class="lineage-stage">
      <p id="lineage-error" role="alert" hidden></p>
      ${topology ? '<section id="invocation-lineage-graph">' : ""}
      <div id="lineage"><div id="lineage-2d" class="lineage-view"></div><div id="lineage-3d" class="lineage-view" hidden></div></div>
      ${topology ? "</section>" : ""}${payload("graph-data", graph)}${payload("graph-style", style)}</div></main>`,
  };
}
