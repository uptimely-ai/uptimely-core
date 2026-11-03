import { badge, contextGroup, contextHeader, contextLink, dataTypeIcon, escape, heading, icon, page } from "./rendering/shared_markup.js";

const LOG_PAGE_SIZE = 1000;
const PREVIEW_TYPE_CATEGORIES = {
  int8: "integer", int16: "integer", int32: "integer", int64: "integer", int128: "integer",
  uint8: "integer", uint16: "integer", uint32: "integer", uint64: "integer",
  float32: "float", float64: "float", decimal: "numeric",
  string: "string", categorical: "string", enum: "string",
  boolean: "boolean", date: "date", datetime: "datetime",
  time: "datetime", duration: "datetime", list: "array", array: "array",
  struct: "object", object: "object",
};

async function responseData(fetchData, url) {
  const response = await fetchData(url, { cache: "no-store" });
  if (!response.ok) {
    if (url === "/api/run" && response.status === 404
        && response.headers.get("content-type")?.includes("application/json")) {
      const body = await response.json();
      if (body.detail?.startsWith("No saved run.")) return null;
      throw new Error(body.detail || `Could not load Engine data (HTTP ${response.status}).`);
    }
    let detail = "";
    if (response.headers.get("content-type")?.includes("application/json")) {
      const body = await response.json();
      detail = body.detail || "";
    }
    throw new Error(detail || `Could not load Engine data (HTTP ${response.status}).`);
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

export async function loadInfo(fetchData, configuration = {}) {
  if (configuration.runDataUrl) return responseData(fetchData, configuration.runDataUrl);
  const run = await responseData(fetchData, "/api/run");
  return { run };
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

export function infoPage({ run }) {
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
  const headers = preview.columns.map(column => {
    const type = column.dtype.split(/[([]/, 1)[0].trim().toLowerCase();
    const typeIcon = dataTypeIcon(PREVIEW_TYPE_CATEGORIES[type], "engine-preview-type-icon");
    return `<th scope="col" title="${escape(column.dtype)}">${escape(column.name)}${typeIcon}
      <span${typeIcon ? ' class="sr-only"' : ""}>${escape(column.dtype)}</span></th>`;
  }).join("");
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
  const { document } = browser;
  const sections = [...document.querySelectorAll(".engine-profile-preview")];
  const links = [...document.querySelectorAll("#preview-context .context-links a[href^='#']")];
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
