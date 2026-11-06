import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../../src/uptimely/explorer/app/static/js/graphs/", import.meta.url);
const load = async name => import(`data:text/javascript;base64,${
  Buffer.from(await readFile(new URL(name, root), "utf8")).toString("base64")
}`);
const { projectFeatureLineage } = await load("feature_projection.js");
const { mountLineageViews } = await load("graph_view_controller.js");

function graphData() {
  return {
    nodes: [
      ...["a", "b", "c", "d", "isolated"].map(id => ({ id, is_operator: false })),
      ...["calculate", "alternative", "read", "write"].map(id => ({
        id: `operator:profile:${id}`, operator_id: id, is_operator: true,
      })),
    ],
    links: [
      { source: "a", target: "operator:profile:calculate" },
      { source: "b", target: "operator:profile:calculate" },
      { source: "operator:profile:calculate", target: "c" },
      { source: "operator:profile:calculate", target: "d" },
      { source: "a", target: "operator:profile:alternative" },
      { source: "operator:profile:alternative", target: "c" },
      { source: "operator:profile:read", target: "a" },
      { source: "d", target: "operator:profile:write" },
      { source: "a", target: "c" },
    ],
  };
}

test("feature projection preserves isolated features, contracts operators and deduplicates provenance", () => {
  const data = graphData();
  const original = structuredClone(data);
  assert.equal(projectFeatureLineage(data, true), data);
  const projected = projectFeatureLineage(data, false);
  assert.deepEqual(projected.nodes.map(node => node.id), ["a", "b", "c", "d", "isolated"]);
  assert.deepEqual(projected.links, [
    { source: "a", target: "c", operator_ids: [
      "operator:profile:alternative", "operator:profile:calculate",
    ] },
    { source: "a", target: "d", operator_ids: ["operator:profile:calculate"] },
    { source: "b", target: "c", operator_ids: ["operator:profile:calculate"] },
    { source: "b", target: "d", operator_ids: ["operator:profile:calculate"] },
  ]);
  assert.deepEqual(data, original);
  assert.deepEqual(projectFeatureLineage({ nodes: [], links: [] }, false), { nodes: [], links: [] });
});

test("projection retains operator identity across profiles and multi-step feature paths", () => {
  const data = {
    nodes: ["a", "b", "c"].map(id => ({ id })).concat(
      ["operator:p1:compute", "operator:p2:compute"].map(id => ({ id, is_operator: true })),
    ),
    links: [
      { source: "a", target: "operator:p1:compute" },
      { source: "operator:p1:compute", target: "b" },
      { source: "b", target: "operator:p2:compute" },
      { source: "operator:p2:compute", target: "c" },
    ],
  };
  assert.deepEqual(projectFeatureLineage(data, false).links, [
    { source: "a", target: "b", operator_ids: ["operator:p1:compute"] },
    { source: "b", target: "c", operator_ids: ["operator:p2:compute"] },
  ]);
});

test("invalid graph endpoints and operator-only paths are explicit errors", () => {
  assert.throws(() => projectFeatureLineage({
    nodes: [{ id: "a" }], links: [{ source: "a", target: "missing" }],
  }, false), /unknown link endpoint/);
  assert.throws(() => projectFeatureLineage({
    nodes: ["a", "b"].map(id => ({ id, is_operator: true })),
    links: [{ source: "a", target: "b" }],
  }, false), /connect operators through features/);
});

class Element extends EventTarget {
  constructor() {
    super();
    this.hidden = false;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
  }
  append(child) { this.children.push(child); child.parent = this; }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  setAttribute(name, value) { this.attributes[name] = value; }
}

function harness(t, { url = "https://example.test/docs/explorer/?view=lineage", fail = () => false,
  projection = projectFeatureLineage } = {}) {
  const names = ["lineage", "lineage-2d", "lineage-3d", "lineage-error", "show-operators",
    "operator-legend", "reset-lineage"];
  const elements = new Map(names.map(name => [name, new Element()]));
  elements.get("lineage-3d").hidden = true;
  const buttons = ["2d", "3d"].map(dimension => {
    const button = new Element();
    button.dataset.dimension = dimension;
    return button;
  });
  const zoom = new Element();
  zoom.dataset.zoom = "1.25";
  const browser = new EventTarget();
  browser.location = new URL(url);
  const entries = [url];
  browser.history = {
    pushState(_state, _title, value) {
      browser.location = new URL(value);
      entries.push(browser.location.href);
    },
  };
  const originals = new Map(["document", "window", "ResizeObserver"].map(name => [name, globalThis[name]]));
  globalThis.document = {
    getElementById: id => elements.get(id),
    querySelectorAll: selector => selector === "[data-dimension]" ? buttons : [zoom],
    createElement: () => new Element(),
  };
  globalThis.window = browser;
  let disconnected = false;
  globalThis.ResizeObserver = class {
    observe() {}
    disconnect() { disconnected = true; }
  };
  t.after(() => {
    for (const [name, value] of originals) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  });
  const data = graphData();
  const canonical = structuredClone(data);
  const views = [];
  let selected = null;
  const create = dimension => (container, workingData, select) => {
    if (fail(dimension, workingData)) throw new Error("Cannot create graph");
    const view = {
      dimension, container, data: workingData, select, resizes: [], selected: null,
      pauses: 0, resumes: 0, destroyed: 0, fits: 0, zooms: [],
      resize(fit) { this.resizes.push(fit); },
      selectNode(id) { this.selected = id; },
      fit() { this.fits++; },
      zoom(factor) { this.zooms.push(factor); },
    };
    view.forceGraph = {
      pauseAnimation() { view.pauses++; },
      resumeAnimation() { view.resumes++; },
      _destructor() { view.destroyed++; },
    };
    // Mirror the visualization library's endpoint and layout mutations.
    workingData.nodes[0].x = 100;
    for (const link of workingData.links) {
      link.source = workingData.nodes.find(node => node.id === link.source);
      link.target = workingData.nodes.find(node => node.id === link.target);
    }
    views.push(view);
    return view;
  };
  const abort = new AbortController();
  t.after(() => abort.abort());
  const component = mountLineageViews(
    data, create("2d"), create("3d"), node => { selected = node; }, abort.signal, projection,
  );
  return {
    data, canonical, views, buttons, elements, browser, entries, component, abort, zoom,
    get selected() { return selected; },
    get disconnected() { return disconnected; },
    toggle() {
      const toggle = elements.get("show-operators");
      toggle.dispatchEvent(new Event("click"));
    },
    navigate(value) {
      browser.location = new URL(value);
      component.update();
    },
  };
}

test("both dimensions switch detail with isolated data, feature selection and cached viewports", t => {
  const app = harness(t);
  const full2D = app.views[0];
  full2D.select(full2D.data.nodes.find(node => node.id === "c"));
  app.toggle();
  const features2D = app.views[1];
  assert.equal(features2D.data.nodes.length, 5);
  assert.equal(features2D.data.links.length, 4);
  assert.equal(app.selected.id, "c");
  assert.equal(features2D.selected, "c");
  assert.equal(full2D.container.hidden, true);
  assert.equal(app.elements.get("operator-legend").hidden, true);
  assert.match(app.browser.location.href, /operators=hide/);
  app.buttons[1].dispatchEvent(new Event("click"));
  const features3D = app.views[2];
  assert.equal(features3D.dimension, "3d");
  assert.equal(features3D.selected, "c");
  assert.equal(app.elements.get("lineage-2d").hidden, true);
  app.toggle();
  const full3D = app.views[3];
  assert.equal(full3D.data.nodes.length, app.data.nodes.length);
  assert.equal(full3D.selected, "c");
  assert.equal(app.elements.get("operator-legend").hidden, false);
  assert.equal(app.buttons[1].attributes["aria-pressed"], "true");
  app.toggle();
  assert.equal(app.views.length, 4);
  assert.equal(features3D.container.hidden, false);
  assert.deepEqual(features3D.resizes, [true, false]);
  app.zoom.dispatchEvent(new Event("click"));
  app.elements.get("reset-lineage").dispatchEvent(new Event("click"));
  assert.deepEqual(features3D.zooms, [1.25]);
  assert.equal(features3D.fits, 1);
  assert.equal(app.selected, null);
  assert.deepEqual(app.data, app.canonical);
  app.abort.abort();
  assert.equal(app.disconnected, true);
  assert.ok(app.views.every(view => view.destroyed === 1));
  const entries = app.entries.length;
  app.toggle();
  assert.equal(app.entries.length, entries);
});

test("URL restores detail on refresh and same-page back/forward without recreating views", t => {
  const app = harness(t, {
    url: "https://example.test/docs/explorer/?view=lineage&operators=hide#selection",
  });
  assert.equal(app.views[0].data.nodes.length, 5);
  assert.equal(app.elements.get("show-operators").attributes["aria-pressed"], "false");
  app.toggle();
  assert.equal(app.browser.location.hash, "#selection");
  const full = app.views[1];
  full.select(full.data.nodes.find(node => node.is_operator));
  app.navigate(app.entries[0]);
  assert.equal(app.selected, null);
  assert.equal(app.elements.get("show-operators").attributes["aria-pressed"], "false");
  assert.equal(app.elements.get("operator-legend").hidden, true);
  app.navigate(app.entries[1]);
  assert.equal(app.elements.get("show-operators").attributes["aria-pressed"], "true");
  assert.equal(app.views.length, 2);
  assert.throws(() => app.navigate("https://example.test/?view=lineage&operators=invalid"),
    /Unknown lineage operator mode/);
});

test("failed detail construction retains the current graph, control state and URL", t => {
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args);
  t.after(() => { console.error = original; });
  const app = harness(t, { fail: (_dimension, data) => data.nodes.length === 5 });
  app.toggle();
  assert.equal(app.views.length, 1);
  assert.equal(app.views[0].container.hidden, false);
  assert.equal(app.elements.get("show-operators").attributes["aria-pressed"], "true");
  assert.equal(app.entries.length, 1);
  assert.equal(app.elements.get("lineage-error").hidden, false);
  assert.match(app.elements.get("lineage-error").textContent, /Cannot create graph/);
  assert.match(app.elements.get("lineage-error").textContent, /current view is still available/);
  assert.equal(errors.length, 1);
});

test("topology ignores feature-only URL options and has no projection controls", t => {
  const app = harness(t, {
    url: "https://example.test/?view=topology&operators=invalid", projection: null,
  });
  assert.equal(app.views[0].data.nodes.length, app.data.nodes.length);
  app.toggle();
  assert.equal(app.views.length, 1);
  assert.equal(app.entries.length, 1);
});
