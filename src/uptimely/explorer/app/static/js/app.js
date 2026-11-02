const FORMAT_VERSION = 1;
const SECTIONS = [
  ["overview", "Overview"],
  ["catalogs", "Catalogs"],
  ["feature-lineage", "Feature lineage"],
  ["invocation-lineage", "Invocation lineage"],
  ["plan", "Plan"],
  ["animation", "Animation"],
];

const navigation = document.getElementById("navigation");
const content = document.getElementById("content");
const loadStatus = document.getElementById("load-status");
const errorStatus = document.getElementById("error-status");
const scopeBadge = document.getElementById("scope-badge");
let explorerData;
let animationTimer;

function element(tag, className = "", text = "") {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== "") item.textContent = text;
  return item;
}

function append(parent, ...children) {
  for (const child of children) {
    if (child instanceof Node) parent.append(child);
    else if (child != null) parent.append(document.createTextNode(String(child)));
  }
  return parent;
}

function button(label, action, className = "button") {
  const item = element("button", className, label);
  item.type = "button";
  item.addEventListener("click", action);
  return item;
}

function entries(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? Object.entries(value)
    : [];
}

function display(value) {
  if (value == null || value === "") return "—";
  return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
}

function heading(title, description) {
  const block = element("header", "page-heading");
  append(block, element("h1", "", title), element("p", "", description));
  return block;
}

function card(title, contents = []) {
  const block = element("section", "card");
  if (title) append(block, element("h2", "", title));
  append(block, ...contents);
  return block;
}

function empty(message) {
  return element("p", "empty", message);
}

function details(values) {
  const list = element("dl", "detail-list");
  for (const [label, value] of values) {
    append(list, element("dt", "", label), element("dd", "", display(value)));
  }
  return list;
}

function renderNavigation(active) {
  navigation.replaceChildren();
  for (const [id, label] of SECTIONS) {
    const link = element("a", "", label);
    link.href = `#${id}`;
    if (id === active) link.setAttribute("aria-current", "page");
    navigation.append(link);
  }
}

function renderOverview(data) {
  const page = element("div");
  append(page, heading(data.project.name || "Untitled analytics project",
    `Spec format ${display(data.project.spec_version)} · Explorer data format ${data.format_version}`));
  const summary = data.catalogs.summary;
  const statistics = [
    ["Entities", summary.entity_count],
    ["Datasets", summary.dataset_count],
    ["Dimensions", summary.dimension_count],
    ["Features", summary.feature_count],
    ["Functions", summary.function_count],
    ["Plan stages", data.plan.stage_count],
    ["Invocations", data.plan.invocation_count],
  ];
  const stats = element("div", "stats");
  for (const [label, value] of statistics) {
    const block = element("section", "card");
    append(block, element("span", "stat-value", display(value)),
      element("span", "stat-label", label));
    stats.append(block);
  }
  const scope = card("Build scope", [
    element("p", "", data.scope.label),
    element("p", "muted", data.scope.is_scoped
      ? "The catalog describes the complete spec; the plan is scoped to the selected outputs."
      : "The plan includes all features."),
  ]);
  append(page, stats, scope);
  return page;
}

function renderCatalogs(data) {
  const page = element("div");
  append(page, heading("Project catalogs", "Browse entities, datasets, dimensions, and functions."));
  const configuration = data.catalogs.configuration;
  const grid = element("div", "grid");
  const entities = entries(configuration.entities);
  const entityCards = entities.map(([id, entity]) => {
    const block = card(entity.name || id);
    const dimensions = entity.dimensions || entity.dimension_ids || [];
    append(block,
      element("p", "item-meta", `ID: ${id}`),
      element("p", "item-meta", `Dimensions: ${dimensions.join(", ") || "none"}`));
    const datasets = entries(entity.datasets);
    const datasetList = element("ul", "item-list");
    for (const [datasetId, dataset] of datasets) {
      const item = element("li");
      append(item,
        element("div", "item-title", dataset.name || datasetId),
        element("div", "item-meta", `ID: ${datasetId}`),
        element("div", "item-meta", `Features: ${entries(dataset.features).map(([name]) => name).join(", ") || "none"}`));
      datasetList.append(item);
    }
    if (datasets.length) append(block, element("h3", "", "Datasets"), datasetList);
    return block;
  });
  grid.append(entityCards.length ? entityCards : empty("No entities are declared."));

  const dimensions = entries(configuration.dimensions);
  const dimensionList = element("ul", "item-list");
  for (const [id, dimension] of dimensions) {
    const item = element("li");
    append(item,
      element("div", "item-title", dimension.name || id),
      element("div", "item-meta", `${id} · ${dimension.type || "unspecified type"}`));
    dimensionList.append(item);
  }
  grid.append(card("Dimensions", [
    dimensions.length ? dimensionList : empty("No dimensions are declared."),
  ]));

  const functions = entries(configuration.functions);
  const functionList = element("ul", "item-list");
  for (const [id, definition] of functions) {
    const item = element("li");
    append(item,
      element("div", "item-title", definition.name || id),
      element("div", "item-meta", `${definition.kind || "function"} · ${id}`));
    if (definition.description) append(item, element("p", "item-meta", definition.description));
    functionList.append(item);
  }
  grid.append(card("Functions", [
    functions.length ? functionList : empty("No functions are declared."),
  ]));
  append(page, grid);
  return page;
}

function renderGraph(data, graphKey, title, description) {
  const graph = data.graphs[graphKey];
  const page = element("div");
  append(page, heading(title, description));
  if (!graph.nodes.length) {
    append(page, empty("This graph has no nodes."));
    return page;
  }
  const selectable = element("ul", "item-list");
  const detailPanel = card("Selected node", [
    element("p", "muted", "Select a node to inspect its metadata."),
  ]);
  const setSelected = (node, selectedButton) => {
    for (const child of selectable.querySelectorAll("button")) {
      child.setAttribute("aria-pressed", String(child === selectedButton));
    }
    detailPanel.replaceChildren(element("h2", "", "Selected node"));
    detailPanel.append(details(entries(node)));
  };
  for (const node of graph.nodes) {
    const item = element("li");
    const select = button(node.label || node.id, () => setSelected(node, select), "selectable");
    select.setAttribute("aria-pressed", "false");
    append(item, select, element("div", "item-meta", node.id));
    selectable.append(item);
  }
  const relations = element("ul", "item-list");
  for (const link of graph.links) {
    const source = graph.nodes.find(node => node.id === link.source);
    const target = graph.nodes.find(node => node.id === link.target);
    const item = element("li", "", `${source?.label || link.source} -> ${target?.label || link.target}`);
    relations.append(item);
  }
  const split = element("div", "split");
  append(split, card("Nodes", [selectable]), detailPanel);
  append(page, split, card("Dependencies", [
    relations.childElementCount ? relations : empty("No dependencies are declared."),
  ]));
  return page;
}

function renderPlan(data) {
  const page = element("div");
  append(page, heading("Execution plan", "Review the compiled stages and invocation details."));
  const summary = details([
    ["Plan version", data.plan.plan_version],
    ["Functions", data.plan.function_count],
    ["Entities", data.plan.entity_count],
    ["Features", data.plan.feature_count],
    ["Dependencies", data.plan.dependency_count],
    ["Maximum parallel invocations", data.plan.max_parallel_invocations],
  ]);
  append(page, card("Plan summary", [summary]));
  if (!data.stages.length) append(page, empty("The plan has no execution stages."));
  for (const stage of data.stages) {
    const block = card(`Stage ${stage.stage}`);
    const list = element("ul", "item-list");
    for (const step of stage.steps) {
      const item = element("li");
      append(item,
        element("div", "item-title", `${step.position}. ${step.title || step.function}`),
        element("div", "item-meta", `${step.function_kind} · ${step.entity} · ${step.dataset || "unassigned dataset"}`),
        element("div", "item-meta", `Inputs: ${step.input_features.join(", ") || "none"}`),
        element("div", "item-meta", `Outputs: ${step.output_features.join(", ") || "none"}`));
      list.append(item);
    }
    append(block, list);
    page.append(block);
  }
  return page;
}

function renderAnimation(data) {
  const page = element("div");
  append(page, heading("Data lineage animation", "Step through how invocations transform dataset columns."));
  const steps = data.animation.stages.flatMap((stage, index) =>
    stage.map(step => ({ ...step, stage: index + 1 })));
  if (!steps.length) {
    append(page, empty("There are no invocation steps to animate."));
    return page;
  }
  const controls = element("div", "controls");
  const stepLabel = element("span", "muted");
  const play = element("button", "", "Play");
  play.type = "button";
  const previous = button("Previous", () => {});
  const next = button("Next", () => {});
  const panel = card("Invocation");
  let index = 0;
  let playing = false;
  const show = () => {
    const step = steps[index];
    panel.replaceChildren(
      element("h2", "", step.function_label || step.function),
      details([
        ["Stage", step.stage],
        ["Entity", step.entity],
        ["Dataset", step.dataset_label || step.dataset],
        ["Action", step.action],
        ["Grain", step.grain],
        ["Dependencies", step.dependencies.join(", ") || "none"],
      ]),
    );
    const columns = element("table", "columns");
    const header = element("tr");
    for (const label of ["Column", "Role", "Type"]) header.append(element("th", "", label));
    const head = element("thead");
    head.append(header);
    const body = element("tbody");
    for (const column of step.columns || []) {
      const row = element("tr");
      for (const value of [column.label || column.name, column.role, column.type]) {
        row.append(element("td", "", display(value)));
      }
      body.append(row);
    }
    columns.append(head, body);
    append(panel, element("h3", "", "Columns"), columns);
    stepLabel.textContent = `Step ${index + 1} of ${steps.length}`;
    previous.disabled = index === 0;
    next.disabled = index === steps.length - 1;
    play.textContent = playing ? "Pause" : index === steps.length - 1 ? "Replay" : "Play";
    play.setAttribute("aria-pressed", String(playing));
  };
  const stop = () => {
    playing = false;
    window.clearInterval(animationTimer);
    animationTimer = undefined;
    show();
  };
  const move = delta => {
    stop();
    index = (index + delta + steps.length) % steps.length;
    show();
  };
  previous.addEventListener("click", () => move(-1));
  next.addEventListener("click", () => move(1));
  play.addEventListener("click", () => {
    if (playing) {
      stop();
      return;
    }
    if (index === steps.length - 1) index = 0;
    playing = true;
    show();
    animationTimer = window.setInterval(() => {
      index += 1;
      if (index >= steps.length) stop();
      else show();
    }, 1200);
  });
  append(controls, previous, play, next, stepLabel);
  append(page, controls, panel);
  show();
  return page;
}

function renderPage() {
  window.clearInterval(animationTimer);
  const section = location.hash.slice(1) || "overview";
  const renderers = {
    overview: () => renderOverview(explorerData),
    catalogs: () => renderCatalogs(explorerData),
    "feature-lineage": () => renderGraph(
      explorerData, "feature_lineage", "Feature lineage",
      "Explore declared feature dependencies and inspect individual nodes."),
    "invocation-lineage": () => renderGraph(
      explorerData, "invocation_lineage", "Invocation lineage",
      "Explore invocation dependencies and inspect individual plan nodes."),
    plan: () => renderPlan(explorerData),
    animation: () => renderAnimation(explorerData),
  };
  const render = renderers[section] || renderers.overview;
  renderNavigation(renderers[section] ? section : "overview");
  content.replaceChildren(render());
  content.hidden = false;
}

async function loadExplorerData() {
  const configuration = window.UTIMELY_EXPLORER_CONFIG;
  if (!configuration || typeof configuration.dataUrl !== "string") {
    throw new Error("Explorer data URL is not configured.");
  }
  const response = await fetch(configuration.dataUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load Explorer data (HTTP ${response.status}).`);
  }
  const data = await response.json();
  if (!data || data.format_version !== FORMAT_VERSION || !data.project || !data.catalogs
      || !data.graphs || !data.plan || !Array.isArray(data.stages) || !data.animation) {
    throw new Error("Explorer data is missing or uses an unsupported format. Rebuild the project.");
  }
  return data;
}

window.addEventListener("hashchange", () => {
  if (explorerData) renderPage();
});

try {
  explorerData = await loadExplorerData();
  document.title = `${explorerData.project.name || "Analytics project"} | Explorer`;
  scopeBadge.textContent = explorerData.scope.label;
  loadStatus.hidden = true;
  renderPage();
} catch (error) {
  loadStatus.hidden = true;
  errorStatus.hidden = false;
  errorStatus.textContent = `${error.message} Build the project with "uptimely project build" and refresh this page.`;
}
