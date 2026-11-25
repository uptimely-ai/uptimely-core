import { contextHeader, distribution, escape, heading, href, icon, page } from "./shared_markup.js";
import { UNASSIGNED_DATASET } from "../lineage/lineage_config.js";

export function dashboard(data, { run = null, test = null } = {}) {
  const summary = data.catalogs.summary;
  const build = data.build || {};
  const featureScope = build.features?.length
    ? `<p>Selected features: ${escape(build.features.join(", "))}</p>` : "";
  const testCounts = (test?.cases || []).reduce((counts, item) => {
    counts[item.status] = (counts[item.status] || 0) + 1;
    return counts;
  }, {});
  const testCaseCount = test?.cases?.length || 0;
  const invocationCount = Object.keys(run?.invocations || {}).length;
  const profileCount = Object.keys(run?.profiles || {}).length;
  const passedCount = testCounts.passed || 0;
  const failedCount = testCounts.failed || 0;
  const errorCount = testCounts.error || 0;
  const buildMetrics = [["Profiles", summary.profile_count], ["Features", summary.feature_count],
    ["Functions", summary.function_count]];
  const testMetrics = test ? [
    ["Cases", testCaseCount],
    ["Passed", passedCount],
    ["Failed", failedCount],
    ["Errors", errorCount],
  ] : [];
  const runMetrics = [
    ["Invocations", invocationCount],
    ["Profiles", profileCount],
    ["Duration", run ? `${run.duration_seconds.toFixed(3)} s` : "—"],
  ];
  const testTone = test?.status === "passed" ? "green"
    : test?.status === "failed" || test?.status === "error" ? "red" : "amber";
  const runTone = run?.status === "succeeded" ? "green"
    : run?.status === "failed" || run?.status === "interrupted" ? "red" : "amber";
  const statusIndicator = (status, tone) => tone === "green"
    ? `<span class="dashboard-status-indicator" role="img" aria-label="${escape(status)}" title="${escape(status)}">
      <i data-lucide="circle-check" class="dashboard-status-icon" aria-hidden="true"></i></span>`
    : `<span class="ui-badge ui-badge--${tone}">${escape(status)}</span>`;
  const testStatus = test ? statusIndicator(test.status, testTone)
    : '<span class="ui-badge">Not run</span>';
  const runStatus = run ? statusIndicator(run.status, runTone)
    : '<span class="ui-badge">Not run</span>';
  const formattedTime = value => {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const pad = number => String(number).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} `
      + `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  };
  const time = value => value
    ? `<time datetime="${escape(value)}">${escape(formattedTime(value))}</time>` : "—";
  const latest = value => `<p class="dashboard-result-meta">${time(value)}</p>`;
  const elapsed = (started, finished) => {
    const duration = (new Date(finished) - new Date(started)) / 1000;
    return started && finished && Number.isFinite(duration) && duration >= 0
      ? `${duration.toFixed(3)} s` : "—";
  };
  const statistics = (metrics, label, className = "") => `<dl class="dashboard-result-stats${className
    ? ` ${escape(className)}` : ""}" aria-label="${escape(label)}">
    ${metrics.map(([name, value]) => `<div data-stat="${escape(name)}" data-value="${escape(value)}">
      <dt>${escape(name)}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>`;
  const details = (label, fields) => `<details class="dashboard-result-details">
    <summary>Details</summary>
    <dl>${fields.map(([name, value]) => `<div><dt>${escape(name)}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>
  </details>`;
  const testProgress = test ? `<div class="dashboard-test-progress" role="img"
    aria-label="${testCaseCount ? `${passedCount} passed, ${failedCount} failed, ${errorCount} errors` : "No test cases"}">
    ${[["passed", passedCount], ["failed", failedCount], ["error", errorCount]]
      .filter(([, count]) => count > 0)
      .map(([status, count]) => `<span class="dashboard-test-progress-${status}" style="flex-grow:${count}"></span>`)
      .join("")}</div>` : "";
  const testDuration = test ? elapsed(test.started_at, test.finished_at) : "—";
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
    <section class="dashboard-results" aria-label="Build and latest results">
      <article class="dashboard-result-card">
        <div class="dashboard-result-heading"><div class="dashboard-result-title">
          <h2>Build</h2>${latest(build.built_at)}</div>
          ${statusIndicator("Succeeded", "green")}</div>
        ${featureScope}
        ${statistics(buildMetrics, "Compiled project counts")}
        ${details("build", [
          ["Uptimely version", build.uptimely_version || "—"],
          ["Build format", build.build_version ?? "—"],
          ["Spec source", build.spec_source || "—"],
          ["Code language", build.code_language || "—"],
        ])}
      </article>
      <article class="dashboard-result-card">
        <div class="dashboard-result-heading"><div class="dashboard-result-title">
          <h2>Test</h2>${latest(test?.finished_at || test?.started_at)}</div>${testStatus}</div>
        ${test ? `${statistics(testMetrics, "Latest test results", "dashboard-result-stats--test")}${testProgress}
          ${details("test", [
            ["Started", formattedTime(test.started_at)],
            ["Finished", formattedTime(test.finished_at)],
            ["Duration", testDuration],
            ["Build fingerprint", test.build?.fingerprint || "—"],
            ...(test.error ? [["Error", test.error]] : []),
          ])}`
          : '<p>No saved test report. Run <code>uptimely test</code> to record test results.</p>'}
      </article>
      <article class="dashboard-result-card">
        <div class="dashboard-result-heading"><div class="dashboard-result-title">
          <h2>Run</h2>${latest(run?.finished_at || run?.started_at)}</div>${runStatus}</div>
        ${run ? `${statistics(runMetrics, "Latest run results")}${details("run", [
          ["Run ID", run.run_id],
          ["Started", formattedTime(run.started_at)],
          ["Finished", formattedTime(run.finished_at)],
          ["Duration", `${run.duration_seconds.toFixed(3)} s`],
          ["Uptimely version", run.uptimely_version],
          ["Runtime validation", run.runtime_validation ? "Enabled" : "Disabled"],
          ["Preview row limit", run.preview_rows],
          ["Build fingerprint", run.build?.fingerprint || "—"],
        ])}`
          : '<p>No saved run. Run <code>uptimely run</code> to record execution results.</p>'}
      </article>
    </section>
  </main>`;
}

export function planOverview(data) {
  const plan = data.plan;
  return page(`<p class="mb-2 font-mono text-[10px] uppercase tracking-[.2em] text-slate-500">Execution plan</p>
    ${heading("Overview", "Plan compiled from the spec, ordered by dependency resolution.", "overview")}
    <section id="plan-overview" class="mb-16">
      <div class="catalog-charts lg:grid-cols-2">${distribution("Invocations by binding role", plan.invocation_role_counts, {
        total: plan.invocation_count,
        labelFormatter: role => role[0].toUpperCase() + role.slice(1),
      })}
        ${distribution("Invocations by stage", data.stages.map(stage => [`Stage ${stage.stage}`, stage.steps.length]), {
          total: plan.invocation_count,
          note: "Invocations in each stage can run independently. Actual parallel execution depends on the engine.",
        })}</div></section>`);
}

export function lineage(data, topology) {
  const title = topology ? "Topology" : "Lineage";
  const key = topology ? "invocation-lineage" : "feature-lineage";
  const panelId = topology ? "invocation-node-details" : "node-details";
  const graphData = topology
    ? { ...data.graphs.invocation_lineage, is_scoped: data.scope?.is_scoped === true }
    : data.graphs.feature_lineage;
  const style = topology ? data.graphs.invocation_style : data.graphs.feature_style;
  const profileCount = new Set(graphData.nodes.filter(node => !node.is_operator)
    .map(node => node.profile_id || UNASSIGNED_DATASET)).size;
  const roles = [...new Set(graphData.nodes.flatMap(node => node.binding_roles || [node.role]).filter(Boolean))];
  const relationships = [...new Set(graphData.nodes.flatMap(node =>
    (node.grain_relationships || []).map(item => item.relationship)).filter(Boolean))];
  const payload = (id, value) => `<script id="${id}" type="application/json">${JSON.stringify(value).replace(/</g, "\\u003c")}</script>`;
  return {
    context: `<aside class="site-context" id="lineage-context" aria-label="${title} context" data-context-label="${title.toLowerCase()}">
      ${contextHeader(title, key, "lineage-context", title.toLowerCase())}
      <div class="lineage-control-groups">
        <div class="lineage-buttons" role="group" aria-label="${title} view">
          <button class="ui-button" type="button" data-dimension="2d" title="Show 2D view" aria-label="Show 2D view" aria-pressed="true" aria-controls="lineage-2d">${icon("view-2d")}</button>
          <button class="ui-button" type="button" data-dimension="3d" title="Show 3D view" aria-label="Show 3D view" aria-pressed="false" aria-controls="lineage-3d">${icon("view-3d")}</button>
        </div>
        ${topology ? `<button class="ui-button lineage-full-toggle" id="show-full-lineage" type="button" aria-label="Select an invocation to change highlight scope" title="Select an invocation to change highlight scope" aria-pressed="true" aria-controls="lineage" disabled><i data-lucide="route" aria-hidden="true"></i></button>`
          : `<button class="ui-button lineage-operator-toggle" id="show-operators" type="button" aria-label="Show operators" title="Show operators" aria-pressed="true" aria-controls="lineage">${icon("operators")}</button>`}
        <div class="lineage-buttons" role="group" aria-label="${title} viewport">
          <button class="ui-button" type="button" data-zoom="1.25" aria-label="Zoom in" title="Zoom in">${icon("zoom-in")}</button>
          <button class="ui-button" type="button" data-zoom="0.8" aria-label="Zoom out" title="Zoom out">${icon("zoom-out")}</button>
          <button class="ui-button lineage-reset" id="reset-lineage" type="button" aria-label="Reset view" title="Reset view" aria-controls="lineage">${icon("reset")}</button>
        </div>
      </div>
      <details class="lineage-legend-panel"><summary>${icon("schema")}<span>Graph legend</span>
        <span class="lineage-legend-count">${profileCount} ${profileCount === 1 ? "profile" : "profiles"}</span>
        <i class="lineage-legend-chevron" data-lucide="chevron-down" aria-hidden="true"></i></summary>
        <div class="legend" aria-label="Graph legend">
        <p class="lineage-legend-note">Colors show profiles, not run status. ${topology ? "Arrows show compiler dependencies, not every dataframe reference." : "Arrows show dependencies."}</p>
        <h3 class="legend-heading">${topology ? "Binding roles" : "Nodes"}</h3>
        <div class="lineage-legend-kinds">${topology
          ? roles.map(role => `<span class="lineage-legend-item">${icon(role === "merge" ? "merge" : "compute")}<span>${escape(role)}</span></span>`).join("")
          : `<span class="lineage-legend-item">${icon("features")}<span>Feature</span></span>
            <span class="lineage-legend-item" id="operator-legend">${icon("operators")}<span>Operator</span></span>`}</div>
        ${topology ? `<h3 class="legend-heading">Grain relationships</h3><div class="lineage-legend-kinds">
          ${relationships.map(relationship => `<span class="lineage-legend-item">${icon(relationship)}<span>${escape(relationship)}</span></span>`).join("")}
        </div>` : ""}
        <h3 class="legend-heading">Profiles</h3>
        <div class="dataset-legend" id="dataset-legend"></div>
        ${topology ? '<p class="lineage-legend-note">Colored nodes add data; gray nodes compute or consume it.</p>' : ""}
        </div></details>
      <div class="lineage-details" id="${panelId}" role="region" aria-label="${topology ? "Invocation details" : "Selected item"}" aria-live="polite">
        <div class="lineage-details-empty">${icon("scope")}<h2>No node selected</h2>
          <p>${topology ? "Select an invocation to inspect its function, arguments, and dependencies." : "Select a feature or operator to inspect its definition and connections."}</p></div>
      </div></aside>`,
    content: `<main class="lineage-workspace"><div class="lineage-stage">
      <p id="lineage-error" role="alert" hidden></p>
      ${topology ? '<section id="invocation-lineage-container">' : ""}
      <div id="lineage"><div id="lineage-2d" class="lineage-view"></div><div id="lineage-3d" class="lineage-view" hidden></div></div>
      ${topology ? "</section>" : ""}${payload("graph-data", graphData)}${payload("lineage-style", style)}</div></main>`,
  };
}
