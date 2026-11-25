import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../../src/uptimely/explorer/app/static/js/", import.meta.url);
const shared = await readFile(new URL("rendering/shared_markup.js", root), "utf8");
const source = await readFile(new URL("engine_pages.js", root), "utf8");
const moduleSource = source.replace(
  "./rendering/shared_markup.js",
  `data:text/javascript;base64,${Buffer.from(shared).toString("base64")}`,
);
const {
  previewPage, initializePreview, infoPage, logsPage, loadDashboard, loadInfo, loadLogs, loadPreviews,
  loadTest, loadTestCases, testInfoPage, testCasesPage, initializeTestCases,
} = await import(
  `data:text/javascript;base64,${Buffer.from(moduleSource).toString("base64")}`
);

const data = {
  catalogs: { configuration: { profiles: {
    first: { name: "Pump readings" }, second: { name: "Daily totals" },
  } } },
};
const preview = {
  status: "succeeded", requested_rows: 10,
  columns: [{ name: "Value", dtype: "Float64" }],
  rows: [[12.5], [null], ["<script>"]],
};

test("test pages group cases by operator within each selectable profile", () => {
  const report = {
    status: "failed", version: 1, started_at: "2026-11-25T00:00:00Z", finished_at: null,
    build: { fingerprint: "build-1", manifest: { features: ["temperature"] } },
    cases: [
      { profile: "first", operator: "aggregate", case: "good", status: "passed",
        data: { inputs: { dataset: [{ value: "<unsafe>" }] }, expected: { return: [{ value: 1 }] } },
        actual: [{ value: 1.000001 }] },
      { profile: "first", operator: "aggregate", case: "bad", status: "failed",
        message: "Mismatch", data: { inputs: { dataset: [{ value: 2 }] }, expected: { return: [{ value: 3 }] } },
        actual: [{ value: 4 }] },
      { profile: "second", operator: "other", case: "old", status: "error", data: null },
    ],
  };
  const info = testInfoPage(report).content;
  assert.match(info, /build-1/);
  assert.match(info, /temperature/);
  assert.match(info, /<dt>Passed<\/dt><dd>1<\/dd>/);
  assert.match(info, /<dt>Failed<\/dt><dd>1<\/dd>/);
  const { context, content } = testCasesPage(data, report);
  assert.match(context, /Pump readings/);
  assert.match(context, /Daily totals/);
  assert.match(context, /<option value="" disabled selected>Choose a profile<\/option>/);
  assert.match(context, /<span>aggregate<\/span>/);
  assert.match(context, /<span class="context-link-label">good<\/span>/);
  assert.match(context, /<span class="context-link-label">bad<\/span>/);
  assert.match(context, /<span>other<\/span>/);
  assert.match(context, /data-test-profile="1" hidden/);
  assert.match(content, /Choose a profile in Cases controls/);
  assert.match(content, /&lt;unsafe&gt;/);
  assert.doesNotMatch(content, /<unsafe>/);
  assert.match(content, /aria-label="Passed" title="Passed"><i data-lucide="circle-check"/);
  assert.match(content, /ui-badge--red">failed/);
  assert.match(content, /Expected output/);
  assert.match(content, /Actual output/);
  for (const [title, icon] of [["Input", "input"], ["Output", "output"],
    ["Expected output", "output"], ["Actual output", "output"]]) {
    assert.match(content, new RegExp(`icon--${icon}[^>]*>\\s*</i><span>${title}</span></h2><div class="ui-table-scroll`));
  }
  assert.match(content, />3<\/td>/);
  assert.match(content, />4<\/td>/);
  assert.match(content, />1\.000001<\/td>/);
  assert.match(content, /Case data is unavailable/);
  assert.match(testInfoPage(null).content, /No saved test/);
  assert.match(testCasesPage(data, null).content, /No saved cases/);
});

test("test profile selection filters operators and follows case history", () => {
  const sections = ["1", "1", "2"].map((profile, index) => ({
    id: `case-${index}`, dataset: { testProfile: profile }, hidden: true, scrollIntoView() {},
  }));
  const links = sections.map(({ id }) => ({
    hash: `#${id}`, attributes: {}, listeners: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    addEventListener(name, callback) { this.listeners[name] = callback; },
  }));
  const groups = ["1", "2"].map(profile => ({ dataset: { testProfile: profile }, hidden: true }));
  const picker = {
    value: "", listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
  };
  const prompt = { hidden: false };
  const listeners = {};
  const browser = {
    location: { hash: "" },
    history: { pushState(_state, _title, hash) { browser.location.hash = hash; } },
    document: {
      getElementById: id => id === "test-profile" ? picker : prompt,
      querySelectorAll: selector => selector === ".engine-test-case" ? sections
        : selector === "#test-cases-context [data-test-profile]" ? groups : links,
    },
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  initializeTestCases(browser, new AbortController().signal);
  assert.deepEqual(sections.map(section => section.hidden), [true, true, true]);
  assert.equal(prompt.hidden, false);
  picker.value = "1";
  picker.listeners.change();
  assert.equal(browser.location.hash, "#case-0");
  assert.deepEqual(groups.map(group => group.hidden), [false, true]);
  assert.deepEqual(sections.map(section => section.hidden), [false, true, true]);
  links[1].listeners.click({ button: 0, preventDefault() {} });
  assert.equal(browser.location.hash, "#case-1");
  assert.equal(links[1].attributes["aria-current"], "location");
  picker.value = "2";
  picker.listeners.change();
  assert.deepEqual(groups.map(group => group.hidden), [true, false]);
  assert.deepEqual(sections.map(section => section.hidden), [true, true, false]);
  browser.location.hash = "#case-1";
  listeners.popstate();
  assert.equal(picker.value, "1");
  assert.deepEqual(sections.map(section => section.hidden), [true, false, true]);
  browser.location.hash = "";
  listeners.hashchange();
  assert.equal(picker.value, "");
  assert.equal(prompt.hidden, false);
});

test("case pages show saved calls above inputs and distinguish injected dataframes", () => {
  const report = { cases: [
    { profile: "first", operator: "aggregate", case: "basic", status: "passed",
      data: { inputs: { dataset: [{ value: 1 }] }, expected: { return: [{ value: 1 }] } },
      call: {
        function: "pump_analytics:aggregate",
        arguments: {
          dataset: "$dataset", literal: "$dataset", options: { "a/b~c": [null, true, "<unsafe>"] },
        },
        dataframe_inputs: { "/dataset": "dataset", "/options/a~1b~0c/0": "dataset" },
      } },
    { profile: "first", operator: "other", case: "empty", status: "error",
      call: { function: "pump:empty", arguments: {} } },
    { profile: "first", operator: "other", case: "old", status: "error" },
  ] };
  const { content } = testCasesPage(data, report);
  assert.match(content, /<code class="language-python">pump_analytics\.aggregate/);
  assert.match(content, /pump_analytics\.aggregate\(\n  dataset=\$dataset,/);
  assert.match(content, /literal=&quot;\$dataset&quot;/);
  assert.match(content, /&quot;a\/b~c&quot;: \[\$dataset, True, &quot;&lt;unsafe&gt;&quot;\]/);
  assert.ok(content.indexOf("pump_analytics.aggregate") < content.indexOf("<span>Input</span>"));
  assert.match(content, /pump\.empty\(\)/);
  assert.match(content, /Function call unavailable\./);
});

test("test data loads through live and static URLs", async () => {
  const urls = [];
  const fetchData = async url => {
    urls.push(url);
    return { ok: true, json: async () => ({ status: "passed", cases: [] }) };
  };
  assert.equal((await loadTest(fetchData)).status, "passed");
  assert.equal((await loadTest(fetchData, { testDataUrl: "./data/test.json" })).status, "passed");
  assert.deepEqual(urls, ["/api/test", "./data/test.json"]);
});

test("case pages load profile artifacts from live and static data", async () => {
  const report = {
    version: 4, started_at: "2026-11-25T00:00:00Z", status: "failed",
    cases: [{ profile: "first", operator: "calculate", case: "basic", status: "failed" }],
  };
  const details = {
    inputs: { dataset: [{ value: 1 }] }, expected: { return: [{ value: 2 }] },
    actual: [{ value: 3 }], call: { function: "example:calculate", arguments: {} },
  };
  const fetched = [];
  const fetchData = async url => {
    fetched.push(url);
    return { ok: true, json: async () => url.endsWith("test.json") || url === "/api/test"
      ? report : { calculate: { cases: { basic: details } } } };
  };
  const live = await loadTestCases(fetchData);
  const exported = await loadTestCases(fetchData, {
    testDataUrl: "./data/test.json", testCasesUrl: "./data/test/cases",
  });
  assert.deepEqual(live.cases[0].data, { inputs: details.inputs, expected: details.expected });
  assert.deepEqual(live.cases[0].actual, details.actual);
  assert.deepEqual(exported, live);
  assert.deepEqual(fetched, [
    "/api/test", "/api/test/cases/first?started_at=2026-11-25T00%3A00%3A00Z",
    "./data/test.json", "./data/test/cases/first.json",
  ]);
  await assert.rejects(loadTestCases(async url => ({
    ok: true, json: async () => url === "/api/test" ? report : {},
  })), /Missing saved test case/);
});

test("exported engine pages load only relative static data without live API requests", async () => {
  const test = { status: "passed", cases: [] };
  const snapshot = {
    run: { run_id: "exported", profiles: { first: {} } },
    logs: Array.from({ length: 1000 }, (_, index) => ({
      level: "debug", logger: "demo", timestamp: "2026-11-03T20:00:00Z",
      message: `Event ${index}`,
    })),
    previews: { first: preview },
  };
  const fetched = [];
  const fetchData = async (url, options) => {
    fetched.push([url, options.cache]);
    return { ok: true, json: async () => url === "./data/test.json" ? test : snapshot };
  };
  const configuration = {
    runDataUrl: "./data/run.json", testDataUrl: "./data/test.json",
  };
  const home = await loadDashboard(fetchData, configuration);
  assert.equal(home.run, snapshot.run);
  assert.equal(home.test, test);
  assert.equal((await loadInfo(fetchData, configuration)).run, snapshot.run);
  const logs = await loadLogs(fetchData, configuration);
  assert.equal(logs.logs.length, 1000);
  assert.doesNotMatch(logsPage(logs).content, /id="load-more-logs"/);
  assert.equal((await loadPreviews(fetchData, configuration)).previews.first, preview);
  assert.deepEqual(fetched, [
    ["./data/run.json", "no-store"], ["./data/test.json", "no-store"],
    ...Array(3).fill(["./data/run.json", "no-store"]),
  ]);
});

test("static run fetch failures are explicit, not disguised as an absent run", async () => {
  const fetchData = async () => ({
    ok: false, status: 404, headers: { get: () => "text/html" },
  });
  for (const load of [loadInfo, loadLogs, loadPreviews]) {
    await assert.rejects(load(fetchData, { runDataUrl: "./data/run.json" }), /HTTP 404/);
  }
  await assert.rejects(loadDashboard(fetchData, {
    runDataUrl: "./data/run.json", testDataUrl: "./data/test.json",
  }), /HTTP 404/);
});

test("live run pages preserve API requests and paginated logs", async () => {
  const run = { run_id: "live", profiles: { first: {} } };
  const logs = Array.from({ length: 1000 }, () => ({
    level: "debug", logger: "demo", timestamp: "", message: "Recorded",
  }));
  const fetched = [];
  const fetchData = async url => {
    fetched.push(url);
    return {
      ok: true,
      json: async () => url === "/api/run" ? run
        : url === "/api/test" ? { status: "passed", cases: [] }
          : url.includes("/logs") ? logs : preview,
    };
  };
  const dashboard = await loadDashboard(fetchData);
  assert.equal(dashboard.run, run);
  assert.equal(dashboard.test.status, "passed");
  assert.equal((await loadInfo(fetchData)).run, run);
  assert.match(logsPage(await loadLogs(fetchData)).content, /id="load-more-logs"/);
  assert.equal((await loadPreviews(fetchData)).previews.first, preview);
  assert.deepEqual(fetched, [
    "/api/run", "/api/test", "/api/run", "/api/run",
    "/api/run/logs?run_id=live&offset=0&limit=1000",
    "/api/run", "/api/run/preview/first?run_id=live",
  ]);
});

test("profile titles replace the generic Preview heading and tables preserve values", () => {
  const { content, context } = previewPage(data, {
    run: { profiles: { first: {}, second: {} } },
    previews: { first: preview, second: preview },
  });
  assert.match(content, /<h1[^>]*>.*Pump readings/);
  assert.match(content, /<h1[^>]*>.*Daily totals/);
  assert.match(content, /<h1[^>]*>.*data-lucide="table-2"/);
  assert.match(content, /<\/h1>\s*<p[^>]*>Dataset produced from the profile<\/p>/);
  assert.doesNotMatch(content, /<h1[^>]*>.*<span>Preview<\/span>/);
  assert.match(content, /id="profile-second" hidden/);
  assert.match(content, /<th scope="col"><span class="typed-name" title="Float64"[^>]*><i data-lucide="hash"[^>]*><\/i><span>Value<\/span><\/span><\/th>/);
  assert.match(content, /class="is-number">12.5/);
  assert.match(content, /class="is-null">null/);
  assert.match(content, /&lt;script&gt;/);
  assert.match(content, /aria-label="Pump readings preview table"/);
  assert.match(context, /Pump readings/);
  assert.match(context, /data-lucide="table-2"/);
});

test("profile switching reveals the selected title and table and preserves history", () => {
  const sections = ["profile-first", "profile-second"].map(id => ({
    id, hidden: false, scrolls: 0,
    scrollIntoView() { this.scrolls++; },
  }));
  const links = sections.map(({ id }) => ({
    hash: `#${id}`, attributes: {}, listeners: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    addEventListener(name, callback) { this.listeners[name] = callback; },
  }));
  const listeners = {};
  const browser = {
    location: { hash: "" },
    document: {
      querySelectorAll(selector) {
        return selector === ".engine-profile-preview" ? sections : links;
      },
    },
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  initializePreview(browser, new AbortController().signal);
  assert.deepEqual(sections.map(section => section.hidden), [false, true]);
  links[1].listeners.click();
  assert.deepEqual(sections.map(section => section.hidden), [true, false]);
  assert.equal(sections[1].scrolls, 1);
  browser.location.hash = "#profile-first";
  listeners.hashchange();
  assert.deepEqual(sections.map(section => section.hidden), [false, true]);
});

test("preview context groups run datasets by available profile categories", () => {
  const categorized = { catalogs: { configuration: { profiles: {
    first: { name: "Pump readings", category: "Telemetry <raw>" },
    second: { name: "Daily totals", category: "Reports" },
    third: { category: "Telemetry <raw>" },
  } } } };
  const run = { profiles: { first: {}, second: {}, third: {}, unknown: {} } };
  const { context } = previewPage(categorized, {
    run, previews: Object.fromEntries(Object.keys(run.profiles).map(id => [id, preview])),
  });
  const groups = [...context.matchAll(/<div class="context-link-group">([\s\S]*?)<\/div>/g)];
  assert.equal(groups.length, 3);
  assert.match(groups[0][1], /Telemetry &lt;raw&gt;/);
  assert.match(groups[0][1], /context-link-count">2</);
  assert.match(groups[0][1], /profile-first/);
  assert.match(groups[0][1], /profile-third/);
  assert.match(groups[1][1], /Reports/);
  assert.match(groups[2][1], /Uncategorized/);
  assert.match(groups[2][1], /profile-unknown/);
  assert.equal((context.match(/data-lucide="table-2"/g) || []).length, 4);
});

test("preview context stays flat when no profile categories are available", () => {
  const { context } = previewPage(data, {
    run: { profiles: { first: {}, second: {} } }, previews: { first: preview, second: preview },
  });
  assert.doesNotMatch(context, /context-link-group/);
});

test("run pages use shared panels and avoid duplicate empty-state icons or misleading log counts", () => {
  for (const result of [
    infoPage({ run: null }),
    logsPage({ run: null, logs: [] }),
    previewPage(data, { run: null, previews: {} }),
  ]) {
    assert.match(result.content, /class="ui-panel engine-empty"/);
    assert.doesNotMatch(result.content, /engine-empty-icon|Engine run/);
  }
  const { content } = logsPage({ run: { run_id: "one" }, logs: [] });
  assert.match(content, /No log events were recorded/);
  assert.doesNotMatch(content, /data-section-count/);
  const rendered = previewPage(data, {
    run: { profiles: { first: {} } }, previews: { first: preview },
  }).content;
  assert.match(rendered, /class="ui-table engine-preview-table"/);
  assert.match(rendered, /class="ui-badge ui-badge--green">succeeded/);
});

test("saved run details show compute and merge outcomes independently", () => {
  const run = {
    status: "failed",
    started_at: "2026-11-07T10:00:00Z",
    finished_at: "2026-11-07T10:00:01Z",
    duration_seconds: 1,
    uptimely_version: "test",
    runtime_validation: true,
    preview_rows: 10,
    run_id: "run-1",
    build: { fingerprint: "fingerprint", manifest: { features: null } },
    invocations: {
      "invocation:merge:join:data:source": {
        status: "failed", duration_seconds: 0.2, error: "Merge failed",
      },
      "invocation:read:load:data:source": {
        status: "succeeded", duration_seconds: 0.1, error: null,
      },
    },
  };
  const stages = [{ steps: [
    {
      invocation_id: "invocation:read:load:data:source",
      phase: "compute", title: "Load data", operator_id: "source",
    },
    {
      invocation_id: "invocation:merge:join:data:source",
      phase: "merge", title: "Join data", operator_id: "source",
    },
  ] }];
  const { content } = infoPage({ run }, stages);
  assert.match(content, /Invocation outcomes/);
  assert.match(content, /data-phase="compute" data-status="succeeded"/);
  assert.match(content, /data-phase="merge" data-status="failed"/);
  assert.match(content, /Join data · source/);
  assert.match(content, /Merge failed/);
});

test("single-profile previews have no context menu and failed previews remain explicit", () => {
  const { context, content } = previewPage(data, {
    run: { profiles: { first: {} } },
    previews: { first: { status: "failed", error: "Collection failed <detail>" } },
  });
  assert.equal(context, "");
  assert.match(content, /Pump readings/);
  assert.match(content, /Collection failed &lt;detail&gt;/);
  assert.doesNotMatch(content, /<table/);
});

test("preview headers put physical datatype icons before column names without type strings", () => {
  const types = [
    ["Int64", "hash"], ["String", "case-sensitive"], ["Boolean", "toggle-left"],
    ["Datetime(time_unit='us', time_zone=None)", "calendar-clock"],
    ["List(Int64)", "brackets"], ["Struct({'x': Int64})", "braces"],
  ];
  for (const [dtype, icon] of types) {
    const { content } = previewPage(data, {
      run: { profiles: { first: {} } },
      previews: { first: {
        ...preview, columns: [{ name: "Value", dtype }], rows: [],
      } },
    });
    assert.ok(content.includes(`data-lucide="${icon}"`), dtype);
    assert.ok(content.includes(`title="${dtype.replaceAll("'", "&#39;")}"`), dtype);
    assert.match(content, /<span>Value<\/span><\/span><\/th>/);
    assert.doesNotMatch(content, /data-type-label-text|engine-preview-type/);
  }
});

test("preview headers use generic icons for unrecognized types and retain type tooltips", () => {
  const { content } = previewPage(data, {
    run: { profiles: { first: {} } },
    previews: { first: {
      ...preview, columns: [{ name: "Value", dtype: "Binary" }], rows: [],
    } },
  });
  assert.match(content, /title="Binary" aria-label="Value \(Binary\)"/);
  assert.doesNotMatch(content, />Binary</);
  assert.match(content, /data-lucide="braces"[^>]*data-type="Binary"/);
});
