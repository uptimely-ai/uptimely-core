import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../../src/uptimely/explorer/app/static/js/lineage/", import.meta.url);
const load = async name => import(`data:text/javascript;base64,${
  Buffer.from(await readFile(new URL(name, root), "utf8")).toString("base64")
}`);
const { projectFeatureLineage } = await load("feature_projection.js");
const { mountLineageViews } = await load("lineage_view_controller.js");
const shared = `data:text/javascript;base64,${Buffer.from(
  await readFile(new URL("../rendering/shared_markup.js", root), "utf8"),
).toString("base64")}`;
const lineageConfig = `data:text/javascript;base64,${Buffer.from(
  await readFile(new URL("lineage_config.js", root), "utf8"),
).toString("base64")}`;
const lineageLayout = `data:text/javascript;base64,${Buffer.from(
  (await readFile(new URL("lineage_layout.js", root), "utf8"))
    .replace("./lineage_config.js", lineageConfig),
).toString("base64")}`;
const lineageComponents = `data:text/javascript;base64,${Buffer.from(
  (await readFile(new URL("lineage_components.js", root), "utf8"))
    .replace("./lineage_config.js", lineageConfig)
    .replace("./lineage_layout.js", lineageLayout)
    .replace("../rendering/shared_markup.js", shared),
).toString("base64")}`;
const { ExplorerLineage } = await import(lineageComponents);
const { prepareLineageLayout, prepareLineageRoutes, lineageLinkRoute } = await import(lineageLayout);

test("feature routes stay straight despite unequal column widths and skipped empty ranks", () => {
  const nodes = [
    { id: "source", x: 0, y: 0, cardWidth: 112, cardHeight: 38, rankRight: 140 },
    { id: "target", x: 500, y: 0, cardWidth: 112, cardHeight: 38, rankLeft: 360 },
    { id: "wide", x: 250, y: 100, cardWidth: 280, cardHeight: 38 },
  ];
  const data = { nodes, links: [{ source: "source", target: "target" }] };
  prepareLineageRoutes(data);
  assert.deepEqual(lineageLinkRoute(data.links[0]), [[56, 0], [444, 0]]);
  nodes[2].y = 0;
  prepareLineageRoutes(data);
  const points = lineageLinkRoute(data.links[0]);
  assert.ok(points.length > 2);
  assert.ok(points.flat().every(Number.isFinite));
  assert.ok(points.some(([, y]) => Math.abs(y) >= 19));
});

test("feature routes avoid cards with operators shown or hidden and mutable endpoints", () => {
  for (const operators of [true, false]) {
    const data = projectFeatureLineage(graphData(), operators);
    const ranks = new Map(data.nodes.map((node, index) => [node.id, index]));
    prepareLineageLayout(data, node => ranks.get(node.id), node => node.id);
    const dependencies = structuredClone(data.links);
    prepareLineageRoutes(data);
    assert.deepEqual(data.links.map(({ routePoints, ...link }) => link), dependencies);
    const nodes = new Map(data.nodes.map(node => [node.id, node]));
    for (const link of data.links) {
      link.source = nodes.get(link.source);
      link.target = nodes.get(link.target);
    }
    prepareLineageRoutes(data);
    for (const link of data.links) {
      for (const [x, y] of lineageLinkRoute(link)) {
        assert.ok(Number.isFinite(x) && Number.isFinite(y));
        for (const node of data.nodes) {
          assert.ok(x <= node.x - node.cardWidth / 2 || x >= node.x + node.cardWidth / 2
            || y <= node.y - node.cardHeight / 2 || y >= node.y + node.cardHeight / 2);
        }
      }
    }
  }
});

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

test("selected feature details render and initialize a data type icon", () => {
  const originalDocument = globalThis.document;
  const originalLucide = globalThis.lucide;
  const createElement = name => ({
    name,
    children: [],
    attributes: {},
    append(...children) { this.children.push(...children); },
    setAttribute(key, value) { this.attributes[key] = value; },
  });
  const panel = {
    children: [],
    replaceChildren(...children) { this.children = children; },
    append(child) { this.children.push(child); },
  };
  const iconRoots = [];
  globalThis.document = {
    createElement,
    createTextNode: text => ({ text }),
  };
  globalThis.lucide = { createIcons: options => iconRoots.push(options.root) };
  try {
    ExplorerLineage.showDetails(panel, "Selected item", [
      { title: "Definition", icon: "sigma", rows: [["Data type", "Float64", "Float64"]] },
    ]);
    const section = panel.children[1];
    assert.equal(section.attributes["aria-label"], "Definition");
    const typeLabel = section.children[1].children[0].children[1];
    const icon = typeLabel.children[0];
    assert.equal(typeLabel.className, "data-type-label");
    assert.equal(typeLabel.children[1].textContent, "Float64");
    assert.equal(icon.attributes["data-lucide"], "hash");
    assert.equal(icon.attributes["data-type"], "Float64");
    assert.deepEqual(iconRoots, [panel]);
  } finally {
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
    if (originalLucide === undefined) delete globalThis.lucide;
    else globalThis.lucide = originalLucide;
  }
});

test("profile legend does not assign merges a separate color", t => {
  const originalDocument = globalThis.document;
  t.after(() => { globalThis.document = originalDocument; });
  globalThis.document = {
    createElement: () => ({ style: { setProperty() {} } }),
  };
  const entries = [];
  const data = { nodes: [{ id: "join", role: "merge", profile_id: "pump" }] };
  ExplorerLineage.prepareDatasetColors(data, { append: item => entries.push(item) },
    { function_color: "#b9c9d8" });
  assert.deepEqual(entries.map(item => item.textContent), ["pump"]);
  assert.equal(data.nodes[0].mergeColor, "#b9c9d8");
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
  querySelector() { return this.children.find(child => child.tagName === "span") || null; }
}

test("invocation cards draw function-kind icons and only the operator subtitle", t => {
  const originals = new Map(["Path2D", "lucide"].map(name => [name, globalThis[name]]));
  t.after(() => {
    for (const [name, value] of originals) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  });
  globalThis.Path2D = class {
    constructor(d) { this.d = d; }
    ellipse(...args) { this.d = args; }
  };
  globalThis.lucide = { icons: {
    GitMerge: [["path", { d: "merge-path" }]],
    Database: [["ellipse", { cx: "12", cy: "5", rx: "9", ry: "3" }]],
    TableProperties: [["path", { d: "vectorize-path" }]],
    Sparkles: [["path", { d: "automatic-path" }]],
  } };
  const labels = [];
  const shapes = [];
  const icons = [];
  const ctx = {
    save() {}, restore() {}, beginPath() {}, fill() {},
    translate() {}, scale() {},
    stroke(path) { if (path) icons.push(path.d); },
    roundRect(...args) { shapes.push(["rect", ...args]); },
    arc(...args) { shapes.push(["circle", ...args]); },
    moveTo(...args) { shapes.push(["move", ...args]); },
    lineTo(...args) { shapes.push(["line", ...args]); },
    closePath() { shapes.push(["close"]); },
    fillText(...args) { labels.push(args); },
  };
  const highlight = { hasSelection: () => false, isSelected: () => false };
  const node = { x: 0, y: 0, cardWidth: 240, cardHeight: 62 };
  ExplorerLineage.drawCard(node, ctx, "Join inputs", "#abc", highlight, false,
    { subtitle: "read", iconName: "git-merge", badgeIconName: "sparkles" });
  assert.equal(labels[0][0], "Join inputs");
  assert.equal(labels[1][0], "read");
  assert.ok(labels[0][2] < node.y && labels[1][2] > node.y);
  shapes.length = 0;
  ExplorerLineage.drawCard(node, ctx, "Read inputs", "#abc", highlight, false, { iconName: "database" });
  assert.equal(shapes.length, 1);
  shapes.length = 0;
  ExplorerLineage.drawCard(node, ctx, "Score", "#abc", highlight, false, { iconName: "table-properties" });
  assert.equal(shapes.length, 1);
  assert.deepEqual(icons, ["merge-path", "automatic-path",
    [12, 5, 9, 3, 0, 0, Math.PI * 2], "vectorize-path"]);
});

test("feature cards and 3D labels draw type icons without adding visible type text", t => {
  const originals = new Map(["Path2D", "lucide", "document", "THREE", "SpriteText"]
    .map(name => [name, globalThis[name]]));
  t.after(() => {
    for (const [name, value] of originals) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  });
  const paths = [];
  globalThis.Path2D = class {
    constructor(d) { this.d = d; paths.push(this); }
    arc(...args) { this.arcArgs = args; }
    roundRect(...args) { this.rectArgs = args; }
    moveTo(...args) { this.start = args; }
    lineTo(...args) { this.end = args; }
  };
  globalThis.lucide = { icons: {
    Hash: [["line", { x1: "4", y1: "9", x2: "20", y2: "9" }]],
    CaseSensitive: [["path", { d: "M1 2" }]],
    ToggleLeft: [["circle", { cx: "9", cy: "12", r: "3" }],
      ["rect", { x: "2", y: "5", width: "20", height: "14", rx: "7" }]],
    Braces: [["path", { d: "M3 4" }]],
  } };
  const strokes = [];
  const labels = [];
  const ctx = {
    save() {}, restore() {}, translate() {}, scale() {}, beginPath() {},
    roundRect() {}, fill() {}, stroke(path) { if (path) strokes.push(path); },
    fillText(text) { labels.push(text); },
  };
  const highlight = {
    hasSelection: () => false, isSelected: () => false,
  };
  for (const type of ["Float64", "String", "Boolean", null]) {
    ExplorerLineage.drawCard({ x: 0, y: 0, cardWidth: 120, cardHeight: 38, data_type: type },
      ctx, "Feature name", "#abc", highlight, true);
  }
  assert.deepEqual(labels, Array(4).fill("Feature name"));
  assert.equal(strokes.length, 5);
  assert.deepEqual(paths[0].start, [4, 9]);
  assert.deepEqual(paths[0].end, [20, 9]);
  assert.equal(paths[1].d, "M1 2");
  assert.deepEqual(paths[2].arcArgs, [9, 12, 3, 0, Math.PI * 2]);
  assert.deepEqual(paths[3].rectArgs, [2, 5, 20, 14, 7]);
  const count = strokes.length;
  ExplorerLineage.drawCard({ x: 0, y: 0, cardWidth: 120, cardHeight: 38 },
    ctx, "Operator", "#abc", highlight);
  assert.equal(strokes.length, count);

  const vector = () => ({ set(...values) { this.values = values; }, x: 20 });
  class Object3D {
    constructor() { this.children = []; this.position = vector(); this.scale = vector(); }
    add(child) { this.children.push(child); }
  }
  globalThis.THREE = {
    Group: Object3D, Sprite: Object3D,
    CanvasTexture: class { constructor(canvas) { this.image = canvas; } },
    SpriteMaterial: class {},
    SRGBColorSpace: "srgb",
  };
  globalThis.SpriteText = class extends Object3D {
    constructor(text) { super(); this.text = text; }
  };
  globalThis.document = { createElement: () => ({ getContext: () => ctx }) };
  const group = ExplorerLineage.labeledMesh({}, "Feature name",
    { label_color: "#fff" }, 14, "String");
  assert.equal(group.children[1].text, "Feature name");
  assert.equal(group.children.length, 3);
  assert.ok(group.children[2].position.values[0] < -group.children[1].scale.x / 2);
  assert.deepEqual(group.children[2].position.values.slice(1), [14, 0]);
  assert.equal(strokes.length, count + 1);
  assert.equal(ExplorerLineage.labeledMesh({}, "Operator", {}, 14).children.length, 2);
});

function harness(t, { url = "https://example.test/docs/explorer/?view=lineage", fail = () => false,
  fullLineageToggle = false,
  projection = projectFeatureLineage } = {}) {
  const names = ["lineage", "lineage-2d", "lineage-3d", "lineage-error", "show-operators",
    "operator-legend", "reset-lineage"];
  const elements = new Map(names.map(name => [name, new Element()]));
  if (fullLineageToggle) elements.set("show-full-lineage", new Element());
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
      setFullLineage(value) { this.fullLineage = value; },
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

test("direct-neighbor highlighting excludes transitive paths and handles mutable endpoints", () => {
  const data = {
    nodes: ["a", "b", "c", "d", "write", "unrelated"].map(id => ({ id })),
    links: [
      { source: "a", target: "b" }, { source: "b", target: "c" },
      { source: "c", target: "d" }, { source: "d", target: "write" },
      { source: "b", target: "write" }, { source: "unrelated", target: "write" },
    ],
  };
  const highlight = ExplorerLineage.createLineageHighlight(data, false);
  const selected = data.nodes.find(node => node.id === "c");
  highlight.select(selected);
  assert.deepEqual(data.nodes.filter(highlight.isNodeHighlighted).map(n => n.id), ["b", "c", "d"]);
  assert.equal(data.links.filter(highlight.isLinkHighlighted).length, 2);
  assert.deepEqual(data.links.filter(highlight.isLinkDirect), data.links.slice(1, 3));
  for (const link of data.links) {
    link.source = data.nodes.find(node => node.id === link.source);
    link.target = data.nodes.find(node => node.id === link.target);
  }
  highlight.setFullLineage(true);
  assert.deepEqual(data.nodes.filter(highlight.isNodeHighlighted).map(n => n.id), ["a", "b", "c", "d", "write"]);
  assert.equal(highlight.isSelected(selected), true);
  assert.equal(highlight.isLinkDirect(data.links[0]), false);
  assert.equal(highlight.isLinkDirect(data.links[1]), true);
  highlight.setFullLineage(false);
  assert.equal(data.links.filter(highlight.isLinkHighlighted).length, 2);
  highlight.select(null);
  assert.equal(highlight.hasSelection(), false);
  assert.equal(data.links.some(highlight.isLinkDirect), false);
  const full = ExplorerLineage.createLineageHighlight(data);
  full.select(selected);
  assert.equal(full.isNodeHighlighted(data.nodes[0]), true);
});

test("quiet topology draws highlighted links after dimmed links and keeps cards on top", t => {
  const original = globalThis.ForceGraph;
  t.after(() => {
    if (original === undefined) delete globalThis.ForceGraph;
    else globalThis.ForceGraph = original;
  });
  const callbacks = {};
  const graph = new Proxy({}, {
    get: (_target, name) => (...args) => { callbacks[name] = args[0]; return graph; },
  });
  globalThis.ForceGraph = () => () => graph;
  const data = {
    nodes: ["source", "selected", "other", "ancestor"].map((id, index) => ({
      id, x: index * 200, y: 0, cardWidth: 100, cardHeight: 38,
    })),
    links: [
      { source: "source", target: "selected", routePoints: [[50, 0], [150, 0]] },
      { source: "source", target: "other", routePoints: [[50, 0], [350, 0]] },
      { source: "ancestor", target: "source", routePoints: [[550, 0], [50, 0]] },
    ],
  };
  const highlight = ExplorerLineage.createLineageHighlight(data);
  highlight.select(data.nodes[1]);
  const order = [];
  ExplorerLineage.createLineage2D({ clientWidth: 800, clientHeight: 600 }, data,
    { quiet_links: true, link_color: "#aaa" }, { bounds: {} }, highlight,
    { label: n => n.id, drawNode: n => order.push(n.id), onSelect() {} });
  const ctx = {
    save() {}, restore() {}, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {},
    fill() {}, arc() {}, stroke() { order.push(this.strokeStyle); },
  };
  callbacks.linkCanvasObject(data.links[0], ctx, 1);
  assert.deepEqual(order, []);
  callbacks.linkCanvasObject(data.links[1], ctx, 1);
  callbacks.onRenderFramePost(ctx, 1);
  assert.deepEqual(order, [ExplorerLineage.LINK_STYLE.dimmedColor,
    ExplorerLineage.LINK_STYLE.transitiveColor,
    ExplorerLineage.LINK_STYLE.highlightColor, "source", "selected", "other", "ancestor"]);
});

test("full lineage toggle updates cached and new dimensions without losing selection", t => {
  const app = harness(t, { fullLineageToggle: true, projection: null });
  const toggle = app.elements.get("show-full-lineage");
  const twoD = app.views[0];
  assert.equal(toggle.disabled, true);
  toggle.dispatchEvent(new Event("click"));
  assert.equal(twoD.fullLineage, true);
  twoD.select(twoD.data.nodes.find(n => n.id === "c"));
  assert.equal(toggle.disabled, false);
  assert.match(toggle.attributes.title, /Click for direct connections/);
  assert.equal(twoD.fullLineage, true);
  toggle.dispatchEvent(new Event("click"));
  assert.equal(twoD.fullLineage, false);
  assert.equal(toggle.attributes["aria-pressed"], "false");
  assert.match(toggle.attributes.title, /Click for full lineage/);
  app.buttons[1].dispatchEvent(new Event("click"));
  const threeD = app.views[1];
  assert.equal(threeD.fullLineage, false);
  assert.equal(threeD.selected, "c");
  toggle.dispatchEvent(new Event("click"));
  assert.equal(threeD.fullLineage, true);
  assert.equal(twoD.fullLineage, true);
  app.buttons[0].dispatchEvent(new Event("click"));
  assert.equal(app.views.length, 2);
  assert.equal(twoD.selected, "c");
  app.elements.get("reset-lineage").dispatchEvent(new Event("click"));
  assert.equal(twoD.selected, null);
  assert.equal(toggle.disabled, true);
  assert.equal(toggle.attributes["aria-pressed"], "true");
});

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
