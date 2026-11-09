import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../../../src/uptimely/explorer/app/static/js/lineage/", import.meta.url);
const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const config = moduleUrl(await readFile(new URL("lineage_config.js", root), "utf8"));
const layoutModule = moduleUrl((await readFile(new URL("lineage_layout.js", root), "utf8"))
  .replace("./lineage_config.js", config));
const { createLineageLinkRenderer, drawLineageLanes, lineageLinkRoute } = await import(layoutModule);
const { invocationRole, invocationColor, invocationContribution, invocationFlowDetails, invocationLabel, isDefaultMerge, prepareInvocationLayout,
  drawMainframeSpines, drawDatasetMarkers } =
  await import(moduleUrl((await readFile(new URL("invocation_layout.js", root), "utf8"))
    .replace("./lineage_config.js", config)
    .replace("./lineage_layout.js", layoutModule)));

function node(id, stage, kind, profile = "pump") {
  const isMerge = kind === "merge";
  const isPublisher = kind === "vectorize";
  const isEffect = kind === "escape";
  return {
    id, stage, role: isMerge ? "merge" : "compute",
    result: isPublisher ? "target" : "fragment",
    function_returns: kind === "write" ? "none" : isEffect ? "any" : "dataframe",
    function_name: id,
    operator_id: id.replace("-merge", ""),
    profile_id: profile, profile_name: `${profile} profile`, datasetColor: "#2dd4bf",
  };
}

function fixture() {
  return {
    nodes: [
      node("read", 1, "read"), node("read-merge", 2, "merge"),
      node("external", 1, "read"), node("external-merge", 2, "merge"),
      node("enrich", 3, "vectorize"), node("write", 4, "write"),
      node("enrich-again", 3, "vectorize"),
      node("effect", 4, "escape", "sink"),
    ],
    links: [
      { source: "read", target: "read-merge", dependency_type: "fragment" },
      { source: "external", target: "external-merge", dependency_type: "fragment" },
      { source: "read-merge", target: "enrich", dependency_type: "feature" },
      { source: "enrich", target: "write", dependency_type: "feature" },
      { source: "enrich", target: "effect", dependency_type: "feature" },
    ],
  };
}

test("invocation roles derive from binding roles, results and return contracts", () => {
  assert.equal(invocationRole(node("merge", 1, "merge")), "merge");
  assert.equal(invocationRole({ role: "merge" }), "merge");
  assert.equal(invocationRole(node("vector", 1, "vectorize")), "enrich");
  assert.equal(invocationRole(node("write", 1, "write")), "sink");
  assert.equal(invocationRole(node("effect", 1, "escape")), "effect");
  assert.equal(invocationRole(node("read", 1, "read")), "compute");
  assert.equal(invocationLabel(node("join", 1, "merge")), "Join");
  assert.equal(invocationLabel(node("score", 1, "vectorize")), "score");
});

test("publishers use the spine color and off-spine invocations use neutral gray", () => {
  for (const kind of ["merge", "vectorize"]) {
    const publisher = node(kind, 1, kind);
    assert.equal(invocationColor(publisher), publisher.datasetColor);
  }
  const colors = ["read", "conform", "expand", "collapse", "write", "escape"]
    .map(kind => invocationColor(node(kind, 1, kind)));
  assert.equal(new Set(colors).size, 1);
  assert.equal(colors[0], "#9fb3c3");
  assert.notEqual(colors[0], node("read", 1, "read").datasetColor);
});

test("default merges use the callable name and an explicit automatic badge predicate", () => {
  const automatic = {
    function_id: "merge_by_grain", role: "merge",
    function_name: "Automatic merge by grain",
  };
  assert.equal(invocationLabel(automatic), "Merge by grain");
  assert.equal(isDefaultMerge(automatic), true);
  const custom = { ...automatic, function_id: "custom_join", function_name: "Join inputs" };
  assert.equal(invocationLabel(custom), "Join inputs");
  assert.equal(isDefaultMerge(custom), false);
  assert.equal(isDefaultMerge({ ...automatic, role: "compute" }), false);
  assert.equal(invocationLabel({ ...custom, function_name: "merge_pump_inputs" }), "Merge pump inputs");
});

test("single-line cards do not reserve space for hidden operation identifiers", () => {
  const short = node("Score", 1, "vectorize");
  short.operator_id = "a_very_long_operation_identifier_that_is_only_shown_in_details";
  const data = { nodes: [short], links: [] };
  prepareInvocationLayout(data);
  assert.equal(short.cardHeight, 38);
  assert.equal(short.cardWidth, 112);
});
test("contribution tooltips describe only declared outputs by invocation role", () => {
  for (const [kind, prefix] of [["merge", "Publishes"], ["vectorize", "Adds"], ["read", "Declared outputs"]]) {
    assert.equal(invocationContribution({ ...node("score", 1, kind), feature: "Pump Health Score" }),
      `${prefix}: Pump Health Score`);
    assert.equal(invocationContribution(node("score", 1, kind)), `${prefix}: none declared`);
  }
  assert.equal(invocationContribution(node("write", 1, "write")), "Declared outputs: none declared");
});
test("selected-node flow notes explain the step, plan markers and connections in short paragraphs", () => {
  for (const kind of ["merge", "vectorize", "read", "write", "escape"]) {
    const details = invocationFlowDetails(node("selected", 1, kind));
    assert.match(details, /not a completed run/);
    assert.match(details, /Brighter arrows connect directly to the selected step/);
    assert.match(details, /Dataset ready/);
    assert.equal(details.split("\n\n").length, 3);
    assert.match(details, kind === "merge" ? /merging them are separate steps/
      : kind === "vectorize" ? /adds calculated columns directly/
      : kind === "write" ? /consumes data without producing a dataframe result/
      : kind === "escape" ? /return value is ignored/
      : /calculates data separately/);
    assert.ok(details.length < 600);
  }
  assert.match(invocationFlowDetails(node("selected", 1, "merge"), true), /Selected outputs ready/);
});
test("profile mainframes separate computes, publishers and effects without changing dependencies", () => {
  const data = fixture();
  const originalLinks = structuredClone(data.links);
  const layout = prepareInvocationLayout(data);
  const lane = layout.lanes.find(lane => lane.id === "pump");
  const byId = new Map(data.nodes.map(node => [node.id, node]));
  assert.equal(lane.name, "pump profile");
  assert.equal((byId.get("enrich").y + byId.get("enrich-again").y) / 2, lane.spineY);
  assert.ok(byId.get("read").y < byId.get("read-merge").y);
  assert.ok(byId.get("write").y > lane.spineY);
  assert.deepEqual(data.links.map(({ routePoints, ...dependency }) => dependency), originalLinks);
  assert.equal(byId.get("read-merge").rank, byId.get("external-merge").rank);
  assert.equal(byId.get("read-merge").x, byId.get("external-merge").x);
  assert.notEqual(byId.get("read-merge").y, byId.get("external-merge").y);
  assert.equal(byId.get("enrich").x, byId.get("enrich-again").x);
  assert.notEqual(byId.get("enrich").y, byId.get("enrich-again").y);
  assert.ok(byId.get("enrich").x > byId.get("read-merge").x);
  for (const n of data.nodes) {
    assert.ok(Number.isFinite(n.x) && Number.isFinite(n.y));
    assert.equal(n.y, n.fy);
    assert.ok(n.y - n.cardHeight / 2 >= -layout.height / 2);
    assert.ok(n.y + n.cardHeight / 2 <= layout.height / 2);
    assert.ok(n.routeY > n.y + n.cardHeight / 2);
  }
  for (const [index, a] of data.nodes.entries()) {
    for (const b of data.nodes.slice(index + 1)) {
      assert.ok(Math.abs(a.x - b.x) >= (a.cardWidth + b.cardWidth) / 2
        || Math.abs(a.y - b.y) >= (a.cardHeight + b.cardHeight) / 2,
      `Overlapping cards: ${a.id}, ${b.id}`);
    }
  }
});

test("sinks and effects share a non-overlapping consumer track within their profile lane", () => {
  const data = {
    nodes: [
      node("publish", 1, "vectorize", "first"),
      node("write-pump", 2, "write", "pump"),
      node("write-copy", 2, "write", "pump"),
      node("notify", 2, "escape", "pump"),
    ],
    links: [],
  };
  const layout = prepareInvocationLayout(data);
  const lane = layout.lanes.find(lane => lane.id === "pump");
  const consumers = data.nodes.filter(node => node.profile_id === "pump").sort((a, b) => a.y - b.y);
  for (const consumer of consumers) {
    assert.ok(consumer.y - consumer.cardHeight / 2 > lane.spineY);
    assert.ok(consumer.y - consumer.cardHeight / 2 >= lane.top - layout.height / 2);
    assert.ok(consumer.y + consumer.cardHeight / 2 <= lane.top + lane.height - layout.height / 2);
    assert.equal(consumer.y, consumer.fy);
    assert.ok(consumer.routeY > consumer.y + consumer.cardHeight / 2);
  }
  for (let index = 1; index < consumers.length; index++) {
    assert.ok(consumers[index].y - consumers[index - 1].y >= consumers[index].cardHeight);
  }
});

test("unlabeled profile-colored group boxes enclose all publishers and intersect the spine", () => {
  const layout = prepareInvocationLayout(fixture());
  const segments = [];
  const labels = [];
  const boxes = [];
  const fills = [];
  let current;
  const ctx = {
    save() {}, restore() {}, beginPath() { current = []; },
    moveTo(x, y) { current.push([x, y]); },
    lineTo(x, y) { current.push([x, y]); },
    stroke() { segments.push(current); },
    fillText(text) { labels.push(text); },
    roundRect(...args) { boxes.push(args); },
    fill() { fills.push({ color: this.fillStyle, opacity: this.globalAlpha }); },
  };
  drawMainframeSpines(layout, ctx, 0);
  assert.deepEqual(labels, []);
  assert.equal(boxes.length, 2);
  assert.equal(segments.filter(segment => segment.length === 0).length, 1,
    "Only the merge-only group has a border; vectorize groups use fill alone");
  assert.ok(fills.every(fill => fill.color === "#2dd4bf"));
  assert.equal(fills[0].opacity, 0.08);
  assert.equal(fills[1].opacity, 0.28, "Vectorize group matches the spine opacity");
  const lane = layout.lanes.find(lane => lane.id === "pump");
  lane.publicationGroups.forEach((nodes, index) => {
    const [x, y, width, height] = boxes[index];
    assert.ok(y < lane.spineY && y + height > lane.spineY);
    for (const node of nodes) {
      assert.ok(x < node.x - node.cardWidth / 2 && x + width > node.x + node.cardWidth / 2);
      assert.ok(y < node.y - node.cardHeight / 2 && y + height > node.y + node.cardHeight / 2);
    }
  });
  assert.ok(segments.flat().flat().every(Number.isFinite));
  for (const [x, y, width, height] of boxes) {
    for (const segment of segments.filter(segment => segment.length === 2)) {
      const [start, end] = segment;
      assert.ok(start[0] <= end[0], "Spine segments progress left to right");
      assert.ok(end[0] <= x || start[0] >= x + width || start[1] <= y || start[1] >= y + height,
        "Spine enters and exits each group without crossing its interior");
    }
  }
});

test("Dataset markers sit outside the grid and remain included in fit bounds", () => {
  const data = fixture();
  const dependencies = structuredClone(data.links);
  const layout = prepareInvocationLayout(data);
  assert.equal(layout.hideLaneLabels, true);
  const left = layout.bounds.x - layout.bounds.width / 2;
  const right = layout.bounds.x + layout.bounds.width / 2;
  for (const lane of layout.lanes) {
    assert.equal(lane.datasetStart.label, lane.name);
    assert.equal(lane.datasetStart.caption, "Dataset");
    assert.equal(lane.datasetStart.y, lane.spineY);
    assert.equal(lane.datasetReady.y, lane.spineY);
    assert.ok(lane.datasetStart.x + lane.datasetStart.width < -layout.gridBounds.width / 2);
    assert.ok(lane.datasetReady.x > layout.gridBounds.width / 2);
    assert.ok(lane.datasetStart.x >= left);
    assert.ok(lane.datasetReady.x + lane.datasetReady.width <= right);
    assert.equal(lane.datasetReady.label, lane.id === "sink" ? "No dataset produced" : "Dataset ready");
    assert.equal(lane.datasetReady.available, lane.id !== "sink");
  }
  assert.deepEqual(data.links.map(({ routePoints, ...link }) => link), dependencies);
  const laneLabels = [];
  drawLineageLanes(layout, {
    save() {}, restore() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
    fillText(text) { laneLabels.push(text); },
  }, 1);
  assert.deepEqual(laneLabels, []);
  const scoped = prepareInvocationLayout({ ...fixture(), is_scoped: true });
  assert.equal(scoped.lanes.find(l => l.id === "pump").datasetReady.label, "Selected outputs ready");
});

test("Dataset start is outlined, ready is filled, and icons and names render without extra nodes", () => {
  const data = { nodes: [node("initialize", 1, "merge")], links: [] };
  const layout = prepareInvocationLayout(data);
  const labels = [];
  const fills = [];
  const icons = [];
  const textPositions = [];
  const badges = [];
  const ctx = {
    save() {}, restore() {}, beginPath() {}, roundRect(...args) { badges.push(args); }, stroke() {},
    moveTo() {}, lineTo() {}, closePath() {},
    fill() { fills.push(this.fillStyle); },
    fillText(text, x) { labels.push(text); textPositions.push({ x, align: this.textAlign }); },
  };
  drawDatasetMarkers(layout, ctx, 1, (...args) => icons.push(args.slice(1)));
  assert.deepEqual(labels, ["pump profile", "Dataset", "Dataset ready"]);
  assert.equal(icons.length, 2);
  assert.ok(icons.every(([name]) => name === "table-2"));
  assert.equal(textPositions[0].align, "right");
  assert.equal(textPositions[1].align, "right");
  assert.ok(textPositions[0].x < icons[0][1]);
  assert.equal(textPositions[2].align, "left");
  assert.ok(textPositions[2].x > icons[1][1]);
  assert.ok(textPositions[2].x < badges[1][0] + badges[1][2]);
  assert.ok(badges[1][2] > badges[0][2], "Ready badge contains both its icon and label");
  assert.equal(fills[0], "#1a2732");
  assert.equal(fills.at(-1), "#2dd4bf");
  assert.equal(data.nodes.length, 1);
});

test("dependency routes and particles remain finite across invocation tracks and profiles", () => {
  const data = fixture();
  prepareInvocationLayout(data);
  const nodes = new Map(data.nodes.map(node => [node.id, node]));
  for (const link of data.links) {
    link.source = nodes.get(link.source);
    link.target = nodes.get(link.target);
  }
  const coordinates = [];
  const ctx = {
    save() {}, restore() {}, beginPath() {}, stroke() {}, closePath() {}, fill() {},
    moveTo(...args) { coordinates.push(...args); },
    lineTo(...args) { coordinates.push(...args); },
    arc(...args) { coordinates.push(...args); },
  };
  const render = createLineageLinkRenderer(data, { link_color: "#aaa" },
    { hasSelection: () => false, isLinkHighlighted: () => false });
  for (const link of data.links) render(link, ctx, 1);
  assert.ok(coordinates.length > 0);
  assert.ok(coordinates.every(Number.isFinite));
  for (const link of data.links) {
    const points = lineageLinkRoute(link);
    for (const [x, y] of points) {
      for (const node of data.nodes) {
        assert.ok(x <= node.x - node.cardWidth / 2 || x >= node.x + node.cardWidth / 2
          || y <= node.y - node.cardHeight / 2 || y >= node.y + node.cardHeight / 2,
        `Route crosses ${node.id}`);
      }
    }
  }
});

test("adjacent publishers have straight arrows and long arrows avoid intervening cards", () => {
  const data = {
    nodes: [
      node("first", 1, "merge"), node("second", 2, "vectorize"),
      node("third", 3, "vectorize"),
    ],
    links: [{ source: "first", target: "second" }, { source: "first", target: "third" }],
  };
  prepareInvocationLayout(data);
  assert.equal(lineageLinkRoute(data.links[0]).length, 2);
  const longRoute = lineageLinkRoute(data.links[1]);
  assert.ok(longRoute.length > 2);
  assert.ok(longRoute.every(point => point.every(Number.isFinite)));
  const middle = data.nodes[1];
  assert.ok(longRoute.some(([, y]) => Math.abs(y - middle.y) >= middle.cardHeight / 2));
});

test("overview links are quiet and static; only selected links animate", () => {
  const data = { nodes: [node("first", 1, "merge"), node("second", 2, "vectorize")],
    links: [{ source: "first", target: "second" }] };
  prepareInvocationLayout(data);
  let highlighted = false;
  let arcs = 0;
  const ctx = {
    save() {}, restore() {}, beginPath() {}, stroke() {}, closePath() {}, fill() {},
    moveTo() {}, lineTo() {}, arc() { arcs++; },
  };
  const render = createLineageLinkRenderer(data, { quiet_links: true, link_color: "#aaa" },
    { hasSelection: () => highlighted, isLinkHighlighted: () => highlighted });
  render(data.links[0], ctx, 1);
  const overviewWidth = ctx.lineWidth;
  assert.equal(arcs, 0);
  assert.ok(ctx.globalAlpha < 1);
  highlighted = true;
  render(data.links[0], ctx, 1);
  assert.equal(arcs, 1);
  assert.ok(ctx.lineWidth > overviewWidth);
});

test("direct dependencies are stronger than transitive lineage without hiding ancestors", () => {
  const data = { nodes: [node("first", 1, "merge"), node("second", 2, "vectorize")],
    links: [{ source: "first", target: "second" }] };
  prepareInvocationLayout(data);
  let direct = true;
  const ctx = {
    save() {}, restore() {}, beginPath() {}, stroke() {}, closePath() {}, fill() {},
    moveTo() {}, lineTo() {}, arc() {},
  };
  const render = createLineageLinkRenderer(data, { quiet_links: true },
    { hasSelection: () => true, isLinkHighlighted: () => true, isLinkDirect: () => direct });
  render(data.links[0], ctx, 1);
  const directWidth = ctx.lineWidth;
  const directColor = ctx.strokeStyle;
  direct = false;
  render(data.links[0], ctx, 1);
  assert.ok(ctx.lineWidth < directWidth && ctx.lineWidth > 0);
  assert.notEqual(ctx.strokeStyle, directColor);
  assert.ok(ctx.globalAlpha >= 0.5);
});

test("overview arrowheads stay visible without exceeding card size when zoomed out", () => {
  const data = { nodes: [node("first", 1, "merge"), node("second", 2, "vectorize")],
    links: [{ source: "first", target: "second" }] };
  prepareInvocationLayout(data);
  let points = [];
  const ctx = {
    save() {}, restore() {}, beginPath() { points = []; }, stroke() {}, closePath() {}, fill() {},
    moveTo(x, y) { points.push([x, y]); }, lineTo(x, y) { points.push([x, y]); },
  };
  const render = createLineageLinkRenderer(data, { quiet_links: true },
    { hasSelection: () => false, isLinkHighlighted: () => false });
  for (const scale of [0.1, 1]) {
    render(data.links[0], ctx, scale);
    const length = Math.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1]);
    assert.ok(length > 0 && length <= data.nodes[1].cardHeight / 3 + 1e-9);
  }
});

test("rounded routes remove repeated and collinear corners without invalid curves", () => {
  const route = lineageLinkRoute({
    routePoints: [[0, 0], [0, 0], [10, 0], [20, 0], [20, 30], [20, 30], [40, 30]],
  });
  assert.ok(route.flat().every(Number.isFinite));
  assert.deepEqual(route[0], [0, 0]);
  assert.deepEqual(route.at(-1), [40, 30]);
  assert.ok(route.every(([x, y]) => x >= 0 && x <= 40 && y >= 0 && y <= 30));
});

test("empty, single-publisher and effect-only graphs keep finite bounds", () => {
  for (const nodes of [[], [node("initialize", 1, "merge")], [node("sink", 1, "write")]]) {
    const data = { nodes, links: [] };
    const layout = prepareInvocationLayout(data);
    assert.ok(Object.values(layout.bounds).every(Number.isFinite));
    assert.ok(layout.bounds.width > 0 && layout.bounds.height > 0);
    if (nodes[0]?.role === "merge") {
      assert.equal(nodes[0].y, layout.lanes[0].spineY);
    }
  }
});
