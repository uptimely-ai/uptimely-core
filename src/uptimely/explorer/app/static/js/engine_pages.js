import { badge, contextGroup, contextHeader, contextLink, escape, heading, icon, page, typedName } from "./rendering/shared_markup.js";

const LOG_PAGE_SIZE = 1000;
async function responseData(fetchData, url) {
  const response = await fetchData(url, { cache: "no-store" });
  if (!response.ok) {
    if (["/api/run", "/api/test"].includes(url) && response.status === 404
        && response.headers.get("content-type")?.includes("application/json")) {
      const body = await response.json();
      if (body.detail?.startsWith("No saved run.")
          || body.detail?.startsWith("No saved test report.")) return null;
      throw new Error(body.detail || `Could not load Explorer data (HTTP ${response.status}).`);
    }
    let detail = "";
    if (response.headers.get("content-type")?.includes("application/json")) {
      const body = await response.json();
      detail = body.detail || "";
    }
    throw new Error(detail || `Could not load Explorer data (HTTP ${response.status}).`);
  }
  return response.json();
}

function runUrl(path, runId, offset = null) {
  const query = new URLSearchParams({ run_id: runId });
  if (offset !== null) {
    query.set("offset", String(offset));
    query.set("limit", String(LOG_PAGE_SIZE));
  }
  return `${path}?${query}`;
}

async function loadLogPage(fetchData, runId, offset = 0) {
  return responseData(fetchData, runUrl("/api/run/logs", runId, offset));
}

export async function loadDashboard(fetchData, configuration = {}) {
  if (configuration.runDataUrl) {
    const [runSnapshot, test] = await Promise.all([
      responseData(fetchData, configuration.runDataUrl),
      configuration.testDataUrl ? responseData(fetchData, configuration.testDataUrl) : null,
    ]);
    return { run: runSnapshot.run, test };
  }
  const [run, test] = await Promise.all([
    responseData(fetchData, "/api/run"),
    responseData(fetchData, "/api/test"),
  ]);
  return { run, test };
}

export async function loadInfo(fetchData, configuration = {}) {
  if (configuration.runDataUrl) return responseData(fetchData, configuration.runDataUrl);
  const run = await responseData(fetchData, "/api/run");
  return { run };
}

export async function loadTest(fetchData, configuration = {}) {
  return responseData(fetchData, configuration.testDataUrl || "/api/test");
}

export async function loadTestCases(fetchData, configuration = {}) {
  const report = await loadTest(fetchData, configuration);
  if (!report || report.version < 4) return report;
  const profiles = [...new Set(report.cases.map(item => item.profile))];
  const files = await Promise.all(profiles.map(async profile => {
    const url = configuration.testDataUrl
      ? `${configuration.testCasesUrl}/${encodeURIComponent(profile)}.json`
      : `/api/test/cases/${encodeURIComponent(profile)}?${new URLSearchParams({ started_at: report.started_at })}`;
    return [profile, await responseData(fetchData, url)];
  }));
  const suites = new Map(files);
  return {
    ...report,
    cases: report.cases.map(item => {
      const operators = suites.get(item.profile);
      const operator = Object.hasOwn(operators, item.operator) ? operators[item.operator] : null;
      const details = operator && Object.hasOwn(operator.cases, item.case)
        ? operator.cases[item.case] : null;
      if (!details) throw new Error(`Missing saved test case: ${item.profile}/${item.operator}/${item.case}`);
      return { ...item, data: { inputs: details.inputs, expected: details.expected },
        actual: details.actual, call: details.call };
    }),
  };
}

export async function loadLogs(fetchData, configuration = {}) {
  if (configuration.runDataUrl) {
    const snapshot = await responseData(fetchData, configuration.runDataUrl);
    return { ...snapshot, staticSnapshot: true };
  }
  const run = await responseData(fetchData, "/api/run");
  if (!run) return { run: null, logs: [] };
  const logs = await loadLogPage(fetchData, run.run_id);
  return { run, logs };
}

export async function loadPreviews(fetchData, configuration = {}) {
  if (configuration.runDataUrl) return responseData(fetchData, configuration.runDataUrl);
  const run = await responseData(fetchData, "/api/run");
  if (!run) return { run: null, previews: {} };
  const profiles = await Promise.all(Object.keys(run.profiles).map(async profileId => {
    const preview = await responseData(
      fetchData,
      runUrl(`/api/run/preview/${encodeURIComponent(profileId)}`, run.run_id),
    );
    return [profileId, preview];
  }));
  return { run, previews: Object.fromEntries(profiles) };
}

const panel = (title, content) => `<section class="ui-panel engine-panel">
  <h2 class="ui-section-title">${escape(title)}</h2>${content}</section>`;
const field = (label, value) => `<div class="engine-field"><dt>${escape(label)}</dt><dd>${escape(value ?? "—")}</dd></div>`;
const formatValue = value => value == null ? "null"
  : typeof value === "object" ? JSON.stringify(value) : String(value);

export function testInfoPage(test) {
  if (!test) {
    return {
      context: "",
      content: page(heading("Info", "Information about the latest saved test.") + `
        <section class="ui-panel engine-empty"><h2>No saved test</h2>
        <p>Run <code>uptimely test</code> to save test results.</p></section>`),
    };
  }
  const counts = (test.cases || []).reduce((result, item) => {
    result[item.status] = (result[item.status] || 0) + 1;
    return result;
  }, {});
  const duration = test.started_at && test.finished_at
    ? (new Date(test.finished_at) - new Date(test.started_at)) / 1000 : NaN;
  const details = `<dl class="engine-fields">
    ${field("Status", test.status)}${field("Started", test.started_at)}
    ${field("Finished", test.finished_at)}
    ${field("Duration", Number.isFinite(duration) && duration >= 0 ? `${duration.toFixed(3)} s` : null)}
    ${field("Cases", test.cases.length)}
    ${field("Passed", counts.passed || 0)}${field("Failed", counts.failed || 0)}
    ${field("Errors", counts.error || 0)}${field("Report version", test.version)}
    ${field("Build fingerprint", test.build?.fingerprint)}
    ${field("Built feature scope", test.build ? test.build.manifest?.features?.join(", ") || "All features" : null)}
    </dl>${test.error ? `<p class="engine-error-text">${escape(test.error)}</p>` : ""}`;
  return {
    context: "",
    content: page(heading("Info", "Information about the latest saved test.") +
      `<section class="engine-run-banner engine-status-${escape(test.status)}">
        <span>Latest test</span><strong>${escape(test.status)}</strong></section>${panel("Test details", details)}`),
  };
}

function caseTable(rows, label) {
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const headers = columns.map(column => `<th scope="col">${escape(column)}</th>`).join("");
  const body = rows.map(row => `<tr>${columns.map(column =>
    `<td>${Object.hasOwn(row, column) ? escape(formatValue(row[column])) : "—"}</td>`).join("")}</tr>`).join("");
  return `<div class="ui-table-scroll engine-preview-surface" tabindex="0" role="region" aria-label="${escape(label)}">
    <table class="ui-table engine-preview-table"><thead><tr>${headers || "<th>No columns</th>"}</tr></thead>
    <tbody>${body || `<tr><td colspan="${Math.max(columns.length, 1)}">No rows.</td></tr>`}</tbody></table></div>`;
}

const casePanel = (title, iconKey, content) => `<section class="engine-case-panel">
  <h2 class="ui-section-title title-with-icon">${icon(iconKey, "engine-case-icon")}<span>${escape(title)}</span></h2>${content}</section>`;

function caseCall(call) {
  if (!call) return casePanel("Function call", "functions", "<p>Function call unavailable.</p>");
  const inputs = call.dataframe_inputs || {};
  const pointerPart = value => String(value).replaceAll("~", "~0").replaceAll("/", "~1");
  const format = (value, pointer) => {
    if (Object.hasOwn(inputs, pointer)) return `$${inputs[pointer]}`;
    if (value === null) return "None";
    if (typeof value === "boolean") return value ? "True" : "False";
    if (Array.isArray(value)) return `[${value.map((item, index) =>
      format(item, `${pointer}/${index}`)).join(", ")}]`;
    if (typeof value === "object") return `{${Object.entries(value).map(([key, item]) =>
      `${JSON.stringify(key)}: ${format(item, `${pointer}/${pointerPart(key)}`)}`).join(", ")}}`;
    return JSON.stringify(value);
  };
  const args = Object.entries(call.arguments).map(([name, value]) =>
    `  ${name}=${format(value, `/${pointerPart(name)}`)},`);
  const functionName = call.function.replace(":", ".");
  const text = args.length ? `${functionName}(\n${args.join("\n")}\n)` : `${functionName}()`;
  return casePanel("Function call", "functions",
    `<pre class="engine-log-editor engine-case-call" tabindex="0"><code class="language-python">${escape(text)}</code></pre>`);
}

export function testCasesPage(data, test) {
  if (!test || !test.cases.length) {
    return {
      context: "",
      content: page(heading("Cases", "Cases from the latest saved test.") + `
        <section class="ui-panel engine-empty"><h2>No saved cases</h2>
        <p>${test?.error ? escape(test.error) : "Run uptimely test to save case results."}</p></section>`),
    };
  }
  const groups = new Map();
  for (const [index, item] of test.cases.entries()) {
    if (!groups.has(item.profile)) groups.set(item.profile, new Map());
    const operators = groups.get(item.profile);
    if (!operators.has(item.operator)) operators.set(item.operator, []);
    operators.get(item.operator).push(contextLink(`case-${index}`, item.case, "cases"));
  }
  const profiles = data.catalogs.configuration.profiles;
  const profileIndexes = new Map([...groups.keys()].map((profile, index) => [profile, String(index + 1)]));
  const context = `<aside class="site-context" id="test-cases-context" aria-label="Test cases context" data-context-label="test cases">
    ${contextHeader("Cases", "cases", "test-cases-context", "test cases")}
    <div class="test-profile-picker"><label for="test-profile">Profile</label>
      <select id="test-profile" required><option value="" disabled selected>Choose a profile</option>
        ${[...groups.keys()].map(profile => `<option value="${profileIndexes.get(profile)}">${escape(profiles[profile]?.name || profile)}</option>`).join("")}
      </select></div>
    <nav class="context-links" aria-label="Test cases by operator">${[...groups].map(([profile, operators]) =>
      `<div data-test-profile="${profileIndexes.get(profile)}" hidden>${[...operators].map(([operator, links]) =>
        contextGroup(operator, links)).join("")}</div>`).join("")}</nav></aside>`;
  const sections = test.cases.map((item, index) => {
    const status = item.status === "passed"
      ? '<span class="engine-case-success" role="img" aria-label="Passed" title="Passed"><i data-lucide="circle-check" aria-hidden="true"></i></span>'
      : badge(item.status, "red");
    const details = item.data
      ? `${Object.entries(item.data.inputs).map(([name, rows]) =>
        casePanel(name === "dataset" ? "Input" : `Input: ${name}`, "input", caseTable(rows, `Input: ${name}`))).join("")}
        ${casePanel(item.status === "passed" ? "Output" : "Expected output", "output",
          caseTable(item.status === "passed" ? item.actual ?? item.data.expected.return : item.data.expected.return,
            item.status === "passed" ? "Output" : "Expected output"))}
        ${item.status === "failed" ? casePanel("Actual output", "output", item.actual === null || item.actual === undefined
          ? "<p>Actual output was not saved for this case.</p>"
          : caseTable(item.actual, "Actual output")) : ""}`
      : '<section class="ui-panel engine-empty"><p>Case data is unavailable. Run uptimely test again to save it.</p></section>';
    return `<section class="engine-test-case" id="case-${index}" data-test-profile="${profileIndexes.get(item.profile)}" hidden>
      <header class="engine-profile-heading"><div><p class="engine-kicker">${escape(item.profile)} / ${escape(item.operator)}</p>
        <h1>${escape(item.case)}</h1></div>${status}</header>
      ${item.message ? `<p class="engine-error-text">${escape(item.message)}</p>` : ""}
      ${caseCall(item.call)}${details}</section>`;
  }).join("");
  return { context, content: page(`<p id="test-profile-prompt" role="status">Choose a profile in Cases controls to view its test cases.</p>${sections}`) };
}

export function initializeTestCases(browser, signal) {
  const { document } = browser;
  const picker = document.getElementById("test-profile");
  if (!picker) return;
  const prompt = document.getElementById("test-profile-prompt");
  const groups = [...document.querySelectorAll("#test-cases-context [data-test-profile]")];
  const sections = [...document.querySelectorAll(".engine-test-case")];
  const links = [...document.querySelectorAll("#test-cases-context .context-links a[href^='#']")];

  const select = (id, scroll = false) => {
    const selected = sections.find(section => section.id === id);
    const profile = selected?.dataset.testProfile || "";
    picker.value = profile;
    prompt.hidden = Boolean(selected);
    for (const group of groups) group.hidden = group.dataset.testProfile !== profile;
    for (const section of sections) section.hidden = section !== selected;
    for (const link of links) {
      if (link.hash.slice(1) === selected?.id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
    if (scroll) selected?.scrollIntoView({ block: "start" });
  };
  const followHash = () => select(browser.location.hash.slice(1));
  picker.addEventListener("change", () => {
    const selected = sections.find(section => section.dataset.testProfile === picker.value);
    if (!selected) return;
    browser.history.pushState(null, "", `#${selected.id}`);
    select(selected.id);
  }, { signal });
  for (const link of links) {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      if (browser.location.hash !== link.hash) browser.history.pushState(null, "", link.hash);
      select(link.hash.slice(1), true);
    }, { signal });
  }
  browser.addEventListener("hashchange", followHash, { signal });
  browser.addEventListener("popstate", followHash, { signal });
  followHash();
}

function logEntry(entry, lineNumber) {
  const level = entry.level.toLowerCase();
  const related = [
    entry.invocation_id && `invocation=${entry.invocation_id}`,
    entry.profile_id && `profile=${entry.profile_id}`,
  ].filter(Boolean);
  return `<article class="engine-log-line" data-level="${escape(level)}">
    <span class="engine-log-gutter" aria-hidden="true">${lineNumber}</span>
    <div class="engine-log-content">
      <div class="engine-log-main">
        <time class="engine-log-timestamp" datetime="${escape(entry.timestamp)}">${escape(entry.timestamp)}</time>
        <span class="engine-log-level">${escape(entry.level.toUpperCase())}</span>
        <code class="engine-log-logger">${escape(entry.logger)}</code>
        <span class="engine-log-separator" aria-hidden="true">—</span>
        <span class="engine-log-message">${escape(entry.message)}</span>
        ${related.length ? `<span class="engine-log-related">${related.map(escape).join(" ")}</span>` : ""}
      </div>
      ${entry.exception ? `<pre class="engine-log-exception">${escape(entry.exception)}</pre>` : ""}
    </div>
  </article>`;
}

export function infoPage({ run }, stages = []) {
  if (!run) {
    return {
      context: "",
      content: page(heading("Info", "Information about the latest saved run.") + `
        <section class="ui-panel engine-empty" id="run-overview">
          <h2>No saved run</h2><p>Run the project with <code>uptimely run</code> to save run information and profile previews.</p>
        </section>`),
    };
  }

  const statusClass = `engine-status-${escape(run.status)}`;
  const planSteps = stages.flatMap(stage => stage.steps);
  const stepsById = new Map(planSteps.map(step => [step.invocation_id, step]));
  const stepPositions = new Map(planSteps.map((step, index) => [step.invocation_id, index]));
  const invocationResults = Object.entries(run.invocations || {}).sort(([first], [second]) => {
    const firstPosition = stepPositions.get(first) ?? Number.MAX_SAFE_INTEGER;
    const secondPosition = stepPositions.get(second) ?? Number.MAX_SAFE_INTEGER;
    return firstPosition - secondPosition || first.localeCompare(second);
  });
  const invocationOutcomes = invocationResults.length ? panel("Invocation outcomes", `
    <ol class="engine-invocation-results">${invocationResults.map(([id, result]) => {
      const step = stepsById.get(id);
      const phase = step?.phase || (id.split(":")[1] === "merge" ? "merge" : "compute");
      const title = step
        ? `${step.title}${step.operator_id ? ` · ${step.operator_id}` : ""}`
        : id;
      const duration = typeof result.duration_seconds === "number"
        ? `${result.duration_seconds.toFixed(3)} s` : "—";
      return `<li class="engine-invocation-result" data-phase="${escape(phase)}" data-status="${escape(result.status)}">
        <div class="engine-invocation-result-heading">
          <div><span class="engine-kicker">${escape(phase)} invocation</span><h3>${escape(title)}</h3></div>
          ${badge(result.status, result.status === "succeeded" ? "green" : result.status === "failed" ? "red" : "amber")}
        </div>
        <p class="engine-invocation-id"><code>${escape(id)}</code><span>Duration: ${escape(duration)}</span></p>
        ${result.error ? `<p class="engine-error-text">${escape(result.error)}</p>` : ""}
      </li>`;
    }).join("")}</ol>`) : "";
  const runDetails = `<dl class="engine-fields">
      ${field("Status", run.status)}${field("Started", run.started_at)}
      ${field("Finished", run.finished_at)}${field("Duration", `${run.duration_seconds.toFixed(3)} s`)}
      ${field("Uptimely version", run.uptimely_version)}${field("Runtime validation", run.runtime_validation)}
      ${field("Preview row limit", run.preview_rows)}${field("Run ID", run.run_id)}
      ${field("Build fingerprint", run.build.fingerprint)}
      ${field("Built feature scope", run.build.manifest.features?.join(", ") || "All features")}
    </dl>
    <div class="engine-run-error">${run.error ? `<p class="engine-error-text">${escape(run.error)}</p>` : ""}</div>`;
  return {
    context: "",
    content: page(`<section id="run-overview">${heading("Info", "Information about the latest saved run.")}
        <section class="engine-run-banner ${statusClass}"><span>Latest run</span><strong>${escape(run.status)}</strong></section>
        ${panel("Run details", runDetails)}
        ${invocationOutcomes}
      </section>`),
  };
}

export function logsPage({ run, logs, staticSnapshot = false }) {
  const logList = logs.map((entry, index) => logEntry(entry, index + 1)).join("");
  const logMore = !staticSnapshot && run && logs.length === LOG_PAGE_SIZE
    ? `<button class="ui-button engine-load-more" id="load-more-logs" type="button"
        data-run-id="${escape(run.run_id)}" data-offset="${logs.length}">Load more log entries</button>` : "";
  const logError = '<p class="engine-error-text" id="run-log-error" role="alert" hidden></p>';
  return {
    context: "",
    content: page(`${heading("Log", "Log events from the latest saved run.", "logs")}
      ${run ? `<section id="run-logs">
        <div class="engine-log-editor" id="run-log-entries" data-log-count="${logs.length}" aria-label="Run log events">
          ${logList || '<p class="engine-log-empty">No log events were recorded.</p>'}</div>
        ${logError}${logMore}
      </section>` : `<section class="ui-panel engine-empty">
        <h2>No saved run</h2><p>Run the project with <code>uptimely run</code> to save a run log.</p>
      </section>`}`),
  };
}

function previewTable(preview, label) {
  if (preview.status === "failed") {
    return `<p class="engine-error-text">${escape(preview.error || "Preview failed without an error message.")}</p>`;
  }
  const headers = preview.columns.map(column =>
    `<th scope="col">${typedName(column.name, column.dtype)}</th>`).join("");
  const rows = preview.rows.map(row => `<tr>${row.map(value =>
    `<td${value === null ? ' class="is-null"' : typeof value === "number" ? ' class="is-number"' : ""}>${escape(formatValue(value))}</td>`).join("")}</tr>`).join("");
  return `<div class="ui-table-scroll engine-preview-surface" tabindex="0" role="region" aria-label="${escape(label)} preview table">
    <table class="ui-table engine-preview-table">
      <caption class="sr-only">${escape(label)} saved profile preview</caption>
      <thead><tr>${headers || "<th>No columns</th>"}</tr></thead>
      <tbody>${rows || `<tr><td colspan="${Math.max(preview.columns.length, 1)}">No rows in this preview.</td></tr>`}</tbody>
    </table></div>`;
}

export function previewPage(data, { run, previews }) {
  if (!run) {
    return {
      context: "",
      content: page(heading("Preview", "Saved output samples from the latest run.") + `
        <section class="ui-panel engine-empty">
          <h2>No saved previews</h2><p>Run the project with <code>uptimely run</code> to save a preview for each profile.</p>
        </section>`),
    };
  }

  const entries = Object.entries(run.profiles);
  const profiles = data.catalogs.configuration.profiles;
  const grouped = entries.some(([id]) => profiles[id]?.category);
  const groups = new Map();
  for (const [id] of entries) {
    const category = profiles[id]?.category || "Uncategorized";
    if (!groups.has(category)) groups.set(category, []);
    const label = profiles[id]?.name || id;
    const target = `profile-${encodeURIComponent(id)}`;
    groups.get(category).push(contextLink(target, label, "datasets"));
  }
  const links = [...groups].map(([category, items]) =>
    grouped ? contextGroup(category, items) : items.join("")).join("");
  const context = entries.length > 1
    ? `<aside class="site-context" id="preview-context" aria-label="Preview context" data-context-label="Preview">
        ${contextHeader("Preview", "preview", "preview-context", "Preview")}
        <nav class="context-links" aria-label="Profiles in this run">${links}</nav></aside>`
    : "";
  const sections = entries.map(([id], index) => {
    const preview = previews[id];
    const profile = data.catalogs.configuration.profiles[id];
    const label = profile?.name || id;
    return `<section class="engine-profile-preview" id="profile-${escape(encodeURIComponent(id))}"${index ? " hidden" : ""}>
      <header class="engine-profile-heading"><div>
        <p class="engine-kicker">Profile preview</p>
        <h1 class="title-with-icon">${icon("datasets", "title-icon")}<span>${escape(label)}</span></h1>
        <p class="engine-profile-description">Dataset produced from the profile</p>
      </div>
        ${badge(preview.status, preview.status === "succeeded" ? "green" : "red")}
      </header>
      ${previewTable(preview, label)}
    </section>`;
  }).join("");
  return {
    context,
    content: page(sections || heading("Preview", "This run has no profile results to preview.")),
  };
}

export function initializePreview(browser, signal) {
  initializeSectionSelection(browser, signal, ".engine-profile-preview", "#preview-context .context-links a[href^='#']");
}

function initializeSectionSelection(browser, signal, sectionSelector, linkSelector) {
  const { document } = browser;
  const sections = [...document.querySelectorAll(sectionSelector)];
  const links = [...document.querySelectorAll(linkSelector)];
  if (!sections.length || !links.length) return;

  const select = (id, scroll = false) => {
    const selected = sections.find(section => section.id === id) || sections[0];
    for (const section of sections) section.hidden = section !== selected;
    for (const link of links) {
      if (decodeURIComponent(link.hash.slice(1)) === selected.id) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }
    }
    if (scroll) selected.scrollIntoView({ block: "start" });
  };
  const selectFromLocation = () => {
    const hash = browser.location.hash.slice(1);
    select(decodeURIComponent(hash), Boolean(hash));
  };

  for (const link of links) {
    link.addEventListener("click", () => {
      select(decodeURIComponent(link.hash.slice(1)), true);
    }, { capture: true, signal });
  }
  browser.addEventListener("hashchange", selectFromLocation, { signal });
  selectFromLocation();
}

export function initializeLogs(browser, signal) {
  const button = browser.document.getElementById("load-more-logs");
  if (!button) return;
  button.addEventListener("click", async () => {
    button.disabled = true;
    const error = browser.document.getElementById("run-log-error");
    error.hidden = true;
    try {
      const offset = Number(button.dataset.offset);
      const entries = await loadLogPage(
        browser.fetch.bind(browser), button.dataset.runId, offset,
      );
      const logEntries = browser.document.getElementById("run-log-entries");
      logEntries.insertAdjacentHTML(
        "beforeend",
        entries.map((entry, index) => logEntry(entry, offset + index + 1)).join(""),
      );
      logEntries.dataset.logCount = String(offset + entries.length);
      button.dataset.offset = String(offset + entries.length);
      button.hidden = entries.length < LOG_PAGE_SIZE;
    } catch (reason) {
      browser.console.error("Unable to load additional Engine logs", reason);
      error.textContent = reason.message;
      error.hidden = false;
    } finally {
      button.disabled = false;
    }
  }, { signal });
}
