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
const { previewPage, initializePreview, infoPage, logsPage } = await import(
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
  assert.match(content, /<th scope="col" title="Float64">Value<i[^>]*data-lucide="hash"[^>]*><\/i>/);
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

test("preview headers map physical datatypes to icons while retaining exact type labels", () => {
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
    assert.ok(content.includes("engine-preview-type-icon"), dtype);
    assert.match(content, /<span class="sr-only">[^<]+<\/span><\/th>/);
  }
});

test("preview headers show datatype names when there is no matching icon", () => {
  const { content } = previewPage(data, {
    run: { profiles: { first: {} } },
    previews: { first: {
      ...preview, columns: [{ name: "Value", dtype: "Binary" }], rows: [],
    } },
  });
  assert.match(content, /<span>Binary<\/span><\/th>/);
});
