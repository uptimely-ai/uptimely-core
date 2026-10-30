(() => {
  const PLAYBACK_INTERVAL_MS = 1200;
  const REDUCED_MOTION_PLAYBACK_INTERVAL_MS = 1800;
  const GROUPING_PHASE = 2;
  const board = document.getElementById("data-lineage-board");
  if (!board) return;
  const allSteps = Array.from(board.querySelectorAll(".data-lineage-step"));
  let steps = [];
  const stages = Array.from(board.querySelectorAll(".data-lineage-stage"));
  const previous = document.getElementById("data-lineage-previous");
  const next = document.getElementById("data-lineage-next");
  const play = document.getElementById("data-lineage-play");
  const stepLinks = Array.from(document.querySelectorAll("[data-animation-step]"));
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const MAX_COLUMN_FRAMES = 6;
  const FOLD_MIN_RUN = 12;
  const CAMERA_CUT_VIEWPORTS = 2;
  const ANCHOR_MAX_SHARE = 0.5;
  const CAMERA_MARGIN_PX = 24;
  const LINK_INSET_PX = 10;
  const NODE_GAP_PX = 4;
  const NODE_LABEL_SIDE = 0.5;
  const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
  // Pages carry only each step's own columns; earlier features are rebuilt here
  // so page size grows linearly with the number of columns.
  const stepTables = new Map();
  const mainTable = document.createElement("table");
  mainTable.className = "data-lineage-table";
  mainTable.dataset.side = "output";
  allSteps.forEach(step => {
    const table = step.querySelector('table[data-side="output"]');
    stepTables.set(step, table);
    table.remove();
  });
  let mainStep = null;
  const minimap = document.createElement("div");
  minimap.className = "data-lineage-minimap";
  minimap.setAttribute("role", "scrollbar");
  minimap.setAttribute("aria-orientation", "horizontal");
  minimap.setAttribute("aria-label", "Main table columns");
  minimap.setAttribute("aria-valuemin", "0");
  minimap.setAttribute("aria-valuemax", "100");
  minimap.tabIndex = 0;
  minimap.title = "Drag, click, scroll, or use the arrow keys to pan the main table.";
  const minimapView = document.createElement("i");
  minimapView.className = "data-lineage-minimap-view";
  minimap.append(minimapView);
  const datasetPicker = document.getElementById("animation-dataset");
  const datasetGroups = Array.from(document.querySelectorAll("[data-animation-dataset]"));
  const datasetSteps = new Map();
  datasetGroups.forEach(group => {
    const ordered = Array.from(group.querySelectorAll("[data-animation-step]"),
      link => document.getElementById(link.hash.slice(1)));
    ordered.forEach(step => datasetSteps.set(step, ordered));
  });
  function tableColumns(table) {
    const columns = new Map();
    Array.from(table.tHead.rows[0].cells).forEach(cell => columns.set(cell.dataset.column, [cell]));
    Array.from(table.tBodies[0].rows).forEach(row => Array.from(row.cells)
      .forEach(cell => columns.get(cell.dataset.column).push(cell)));
    return columns;
  }
  function existingColumn(header, rowCount) {
    const heading = header.cloneNode(true);
    heading.dataset.role = "Existing";
    heading.removeAttribute("class");
    const cells = Array.from({ length: rowCount }, (_, row) => {
      const cell = document.createElement("td");
      cell.dataset.role = "Existing";
      cell.dataset.column = header.dataset.column;
      const value = document.createElement("span");
      value.className = "data-lineage-cell";
      value.textContent = `Result ${row + 1}`;
      cell.append(value);
      return cell;
    });
    return [heading, ...cells];
  }
  // Replace long runs of earlier features with one expandable column, like a game impostor.
  const folds = new Map();
  function foldColumn(run, rowCount) {
    const header = document.createElement("th");
    header.scope = "col";
    header.dataset.role = "Existing";
    header.dataset.fold = "";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "data-lineage-fold";
    button.textContent = `+${run.length}`;
    const names = run.map(cells => cells[0].dataset.column);
    button.setAttribute("aria-label", `Show ${run.length} earlier features`);
    button.title = `${run.length} earlier features: ${names.slice(0, 5).join(", ")}`
      + `${names.length > 5 ? ", …" : ""}. Click to show them.`;
    header.append(button);
    const cells = Array.from({ length: rowCount }, () => {
      const cell = document.createElement("td");
      cell.dataset.role = "Existing";
      cell.dataset.fold = "";
      const value = document.createElement("span");
      value.className = "data-lineage-cell";
      cell.append(value);
      return cell;
    });
    folds.set(header, run);
    return [header, ...cells];
  }
  function foldRuns(ordered, rowCount) {
    const result = [];
    let run = [];
    const flush = () => {
      if (run.length >= FOLD_MIN_RUN) result.push(foldColumn(run, rowCount));
      else result.push(...run);
      run = [];
    };
    ordered.forEach(cells => {
      if (cells[0].dataset.role === "Existing") run.push(cells);
      else { flush(); result.push(cells); }
    });
    flush();
    return result;
  }
  function unfold(header) {
    const run = folds.get(header);
    const column = header.cellIndex;
    Array.from(mainTable.rows).forEach((row, position) =>
      row.cells[column].replaceWith(...run.map(cells => cells[position])));
    folds.delete(header);
    anchorKeys(mainTable);
    updateMinimap();
    updateLinks();
  }
  mainTable.addEventListener("click", event => {
    const button = event.target.closest(".data-lineage-fold");
    if (button) unfold(button.closest("th"));
  });
  function buildMainTable(step) {
    const base = stepTables.get(step);
    const own = tableColumns(base.cloneNode(true));
    const earlier = new Map();
    for (const previousStep of datasetSteps.get(step) || [step]) {
      if (previousStep === step) break;
      stepTables.get(previousStep).querySelectorAll('thead th[data-role="Output"]')
        .forEach(header => earlier.set(header.dataset.column, header));
    }
    const rowCount = base.tBodies[0].rows.length;
    const ordered = [];
    const placed = new Set();
    const place = (name, cells) => { ordered.push(cells); placed.add(name); };
    own.forEach((cells, name) => { if (cells[0].dataset.role === "Dimension") place(name, cells); });
    earlier.forEach((header, name) => {
      const cells = own.get(name);
      if (!cells) place(name, existingColumn(header, rowCount));
      else if (cells[0].dataset.role !== "Output") place(name, cells);
    });
    own.forEach((cells, name) => {
      if (!placed.has(name) && cells[0].dataset.role !== "Output") place(name, cells);
    });
    own.forEach((cells, name) => { if (!placed.has(name)) place(name, cells); });
    const head = document.createElement("tr");
    const rows = Array.from({ length: rowCount }, () => document.createElement("tr"));
    folds.clear();
    foldRuns(ordered, rowCount).forEach(cells => {
      head.append(cells[0]);
      rows.forEach((row, position) => row.append(cells[position + 1]));
    });
    const thead = document.createElement("thead");
    thead.append(head);
    const tbody = document.createElement("tbody");
    tbody.append(...rows);
    mainTable.replaceChildren(thead, tbody);
  }
  const datasetPrompt = document.getElementById("animation-dataset-prompt");
  let index = 0;
  let phase = 0;
  let playing = false;
  let timer = null;
  let renderedFrame = "";
  function frames() {
    const step = steps[index];
    if (mainStep !== step) {
      buildMainTable(step);
      const viewport = step.querySelector(".data-lineage-panel-output .data-lineage-table-scroll");
      viewport.append(mainTable);
      viewport.after(minimap);
      viewport.scrollLeft = 0;
      mainStep = step;
      buildLinks(step);
    }
    const table = step.querySelector('table[data-side="output"]');
    const preparation = [{ type: "inputs" }];
    if (step.dataset.functionKind === "collapse") preparation.push({ type: "group" });
    preparation.push({ type: "invocation" });
    if (step.dataset.functionKind === "write") preparation.push({ type: "write" });
    if (!table) {
      return preparation;
    }
    // A table that starts empty is summoned row by row; otherwise new columns slide in.
    if (!table.querySelector('th[data-role="Existing"], th[data-role="Input"]')) {
      return [...preparation,
        ...Array.from(table.querySelectorAll("tbody tr"), row => ({ type: "row", element: row }))];
    }
    const headers = Array.from(table.querySelectorAll('thead th[data-role="Output"]'));
    const batchSize = Math.ceil(headers.length / MAX_COLUMN_FRAMES);
    const batches = [];
    for (let start = 0; start < headers.length; start += batchSize) {
      batches.push({ type: "column", elements: headers.slice(start, start + batchSize) });
    }
    return [...preparation, ...batches];
  }
  function renderInput(step, completed) {
    step.querySelectorAll('table[data-side="input"]').forEach(input =>
      renderInputTable(input, step, completed));
    step.querySelectorAll('table[data-side="output"] [data-role="Input"]').forEach(cell =>
      cell.classList.toggle("data-lineage-input-active", phase > 0 && !completed));
  }
  function renderInputTable(input, step, completed) {
    const isCollapse = step.dataset.functionKind === "collapse";
    input.classList.toggle("data-lineage-grouped",
      phase >= GROUPING_PHASE && isCollapse && !completed);
    input.querySelectorAll("[data-role]").forEach(cell => {
      cell.classList.toggle("data-lineage-input-active",
        phase > 0 && !completed && cell.dataset.role === "Input");
      cell.classList.toggle("data-lineage-group-key",
        phase >= GROUPING_PHASE && !completed && isCollapse && cell.hasAttribute("data-join-key"));
    });
  }
  function renderOutputTable(step, sequence, completed) {
    const table = step.querySelector('table[data-side="output"]');
    if (!table) return null;
    const shown = sequence.slice(0, phase);
    const byRow = sequence.some(frame => frame.type === "row");
    const visibleColumns = new Set(shown
      .filter(frame => frame.type === "column")
      .flatMap(frame => frame.elements.map(element => element.cellIndex)));
    const visibleRows = new Set(shown.filter(frame => frame.type === "row").map(frame => frame.element));
    table.querySelectorAll("tr").forEach(row => {
      Array.from(row.cells).forEach((cell, column) => {
        cell.hidden = !byRow && cell.dataset.role === "Output" && !completed
          && !visibleColumns.has(column);
      });
    });
    table.querySelectorAll("tbody tr").forEach(row => {
      row.hidden = byRow && !completed && !visibleRows.has(row);
    });
    table.hidden = false;
    table.parentElement.hidden = false;
    return table;
  }
  function columnBounds(viewport, cell) {
    const left = cell.getBoundingClientRect().left - viewport.getBoundingClientRect().left
      + viewport.scrollLeft;
    return { left, right: left + cell.offsetWidth };
  }
  // Keep row keys pinned, like a game HUD, only when they leave room for the scene.
  function anchorKeys(table) {
    const viewport = table.parentElement;
    const keys = Array.from(table.querySelectorAll('thead th[data-role="Dimension"]'));
    table.querySelectorAll("[data-anchor]").forEach(cell => {
      cell.removeAttribute("data-anchor");
      cell.removeAttribute("data-anchor-edge");
      cell.style.left = "";
    });
    table.classList.remove("data-lineage-overflow");
    viewport.removeAttribute("data-anchored");
    if (viewport.scrollWidth > viewport.clientWidth + 1) {
      table.classList.add("data-lineage-overflow");
    }
    if (!keys.length) return 0;
    const width = keys.reduce((total, key) => total + key.offsetWidth, 0);
    if (width > viewport.clientWidth * ANCHOR_MAX_SHARE) return 0;
    let left = 0;
    keys.forEach((key, position) => {
      table.querySelectorAll("tr").forEach(row => {
        const cell = row.cells[key.cellIndex];
        cell.setAttribute("data-anchor", "");
        if (position === keys.length - 1) cell.setAttribute("data-anchor-edge", "");
        cell.style.left = `${left}px`;
      });
      left += key.offsetWidth;
    });
    viewport.setAttribute("data-anchored", "");
    return width;
  }
  function cameraTargets(table, frame, completed) {
    if (frame?.type === "column") return frame.elements;
    const active = Array.from(table.querySelectorAll("thead th.data-lineage-input-active"));
    if (phase > 0 && !completed && active.length) return active;
    const outputs = Array.from(table.querySelectorAll('thead th[data-role="Output"]'))
      .filter(cell => !cell.hidden);
    return outputs.length ? outputs : Array.from(table.querySelectorAll('thead th[data-role="Input"]'));
  }
  // Follow the action like a game camera, without moving the page itself.
  function followCamera(table, frame, completed, anchorWidth) {
    const viewport = table.parentElement;
    const targets = cameraTargets(table, frame, completed);
    if (!targets.length || viewport.scrollWidth <= viewport.clientWidth) return;
    const bounds = targets.map(cell => columnBounds(viewport, cell));
    const left = Math.min(...bounds.map(bound => bound.left));
    const right = Math.max(...bounds.map(bound => bound.right));
    const viewLeft = viewport.scrollLeft + anchorWidth;
    const viewRight = viewport.scrollLeft + viewport.clientWidth;
    if (left >= viewLeft && right <= viewRight) return;
    const room = viewport.clientWidth - anchorWidth;
    const target = Math.max(0, right - left + CAMERA_MARGIN_PX * 2 > room
      ? left - anchorWidth - CAMERA_MARGIN_PX
      : (left + right) / 2 - anchorWidth - room / 2);
    // Pan short distances; cut to distant targets so the camera never lags behind playback.
    const near = Math.abs(target - viewport.scrollLeft) <= viewport.clientWidth * CAMERA_CUT_VIEWPORTS;
    viewport.scrollTo({
      left: target,
      behavior: playing && near && !reducedMotion.matches ? "smooth" : "instant",
    });
  }
  function updateMinimap() {
    const viewport = mainTable.parentElement;
    if (!viewport) return;
    const range = viewport.scrollWidth - viewport.clientWidth;
    minimap.hidden = range <= 1;
    viewport.toggleAttribute("data-more-left", !minimap.hidden && viewport.scrollLeft > 1);
    viewport.toggleAttribute("data-more-right", !minimap.hidden && viewport.scrollLeft < range - 1);
    if (minimap.hidden) return;
    minimap.setAttribute("aria-controls", viewport.id);
    minimap.setAttribute("aria-valuenow", String(Math.round(viewport.scrollLeft / range * 100)));
    minimapView.style.left = `${viewport.scrollLeft / viewport.scrollWidth * 100}%`;
    minimapView.style.width = `${viewport.clientWidth / viewport.scrollWidth * 100}%`;
  }
  // The overview doubles as the scrollbar: grab the lens to drag, or click the track to glide there.
  let grab = null;
  function minimapShare(event) {
    const bounds = minimap.getBoundingClientRect();
    return (event.clientX - bounds.left) / bounds.width;
  }
  function pan(left, glide) {
    mainTable.parentElement.scrollTo({ left, behavior: glide && !reducedMotion.matches ? "smooth" : "instant" });
  }
  minimap.addEventListener("pointerdown", event => {
    if (event.button !== 0) return;
    event.preventDefault();
    const viewport = mainTable.parentElement;
    const share = minimapShare(event);
    const onLens = event.target === minimapView;
    grab = onLens
      ? share - viewport.scrollLeft / viewport.scrollWidth
      : viewport.clientWidth / viewport.scrollWidth / 2;
    minimap.setPointerCapture(event.pointerId);
    minimap.classList.add("is-dragging");
    if (!onLens) pan((share - grab) * viewport.scrollWidth, true);
  });
  minimap.addEventListener("pointermove", event => {
    if (grab === null) return;
    pan((minimapShare(event) - grab) * mainTable.parentElement.scrollWidth, false);
  });
  ["pointerup", "pointercancel"].forEach(type => minimap.addEventListener(type, () => {
    grab = null;
    minimap.classList.remove("is-dragging");
  }));
  minimap.addEventListener("wheel", event => {
    event.preventDefault();
    const viewport = mainTable.parentElement;
    viewport.scrollLeft += Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
  }, { passive: false });
  minimap.addEventListener("keydown", event => {
    const viewport = mainTable.parentElement;
    const step = {
      ArrowLeft: -viewport.clientWidth / 4,
      ArrowRight: viewport.clientWidth / 4,
      PageUp: -viewport.clientWidth,
      PageDown: viewport.clientWidth,
    }[event.key];
    if (step !== undefined) pan(viewport.scrollLeft + step, true);
    else if (event.key === "Home") pan(0, true);
    else if (event.key === "End") pan(viewport.scrollWidth, true);
    else return;
    event.preventDefault();
  });
  allSteps.forEach(step => {
    const viewport = step.querySelector(".data-lineage-panel-output .data-lineage-table-scroll");
    viewport.id = `${step.id}-main-view`;
    viewport.addEventListener("scroll", updateMinimap, { passive: true });
    viewport.addEventListener("scroll", updateLinks, { passive: true });
    step.querySelectorAll(".data-lineage-sources .data-lineage-table-scroll")
      .forEach(source => source.addEventListener("scroll", updateLinks, { passive: true }));
  });
  // Lineage tethers: shared keys join foreign tables, and feature edges run through the function node.
  const linkLayers = new Map();
  allSteps.forEach(step => {
    const layer = svgElement("svg", { class: "data-lineage-links", "aria-hidden": "true" });
    const defs = svgElement("defs", {});
    ["input", "output"].forEach(kind => {
      const marker = svgElement("marker", {
        id: `${step.id}-${kind}-head`, viewBox: "0 0 10 10", refX: "8", refY: "5",
        markerWidth: "6", markerHeight: "6", orient: "auto",
      });
      marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "data-lineage-head" }));
      defs.append(marker);
    });
    layer.append(defs);
    step.querySelector(".data-lineage-scene").prepend(layer);
    linkLayers.set(step, layer);
  });
  let links = [];
  function svgElement(name, attributes) {
    const element = document.createElementNS(SVG_NAMESPACE, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }
  function linkPoint(cell, edgeElement, viewport, origin, edge) {
    const box = cell.getBoundingClientRect();
    const view = viewport.getBoundingClientRect();
    const center = box.left + box.width / 2;
    const x = Math.min(Math.max(center, view.left + LINK_INSET_PX), view.right - LINK_INSET_PX);
    const edgeBox = edgeElement.getBoundingClientRect();
    return {
      x: x - origin.left,
      y: (edge === "top" ? edgeBox.top : edgeBox.bottom) - origin.top,
      clipped: Math.abs(x - center) > 0.5,
    };
  }
  // Point on the function node's rim facing another point, so edges meet the node like a graph.
  function nodePoint(node, origin, toward) {
    const box = node.getBoundingClientRect();
    const center = { x: box.left + box.width / 2 - origin.left, y: box.top + box.height / 2 - origin.top };
    const dx = toward.x - center.x;
    const dy = toward.y - center.y;
    const length = Math.hypot(dx, dy) || 1;
    // Keep edges clear of the kind label on the node's right side.
    const normal = dx / length > NODE_LABEL_SIDE
      ? { x: NODE_LABEL_SIDE, y: Math.sign(dy || -1) * Math.sqrt(1 - NODE_LABEL_SIDE ** 2) }
      : { x: dx / length, y: dy / length };
    const radius = box.width / 2 + NODE_GAP_PX;
    return { x: center.x + normal.x * radius, y: center.y + normal.y * radius, normal };
  }
  function addLink(layer, kind, label, attributes) {
    const group = svgElement("g", { "data-link": kind });
    const title = svgElement("title", {});
    title.textContent = label;
    const path = svgElement("path", attributes);
    // Hand over from the one-off draw-in to the continuous data flow once a new edge is drawn.
    path.addEventListener("animationend", () => group.classList.remove("is-new"));
    group.append(title, path);
    layer.append(group);
    return { layer, kind, group, path };
  }
  function buildLinks(step) {
    linkLayers.forEach(layer => layer.querySelectorAll(":scope > g").forEach(group => group.remove()));
    links = [];
    const layer = linkLayers.get(step);
    const node = step.querySelector(".data-lineage-node");
    const targets = new Map(Array.from(mainTable.querySelectorAll("thead th[data-join-key]"),
      header => [header.dataset.column, header]));
    const sources = Array.from(step.querySelectorAll('table[data-side="input"]'));
    sources.forEach(source => {
      source.querySelectorAll("thead th[data-join-key]").forEach(header => {
        const target = targets.get(header.dataset.column);
        if (!target) return;
        const link = addLink(layer, "join", `Joined on dimension: ${header.dataset.column}`, {});
        link.start = svgElement("circle", { r: "3.5" });
        link.end = svgElement("circle", { r: "3.5" });
        link.group.append(link.start, link.end);
        links.push({ ...link, source, header, target });
      });
    });
    const inputs = [
      ...Array.from(mainTable.querySelectorAll('thead th[data-role="Input"]'),
        cell => ({ cell, table: mainTable, edge: "bottom" })),
      ...sources.flatMap(source => Array.from(source.querySelectorAll('thead th[data-role="Input"]'),
        cell => ({ cell, table: source, edge: "top" }))),
    ];
    const boundary = step.querySelector("[data-write-boundary]");
    if (boundary) links.push({ boundary, node,
      ...addLink(layer, "write", `Write: ${boundary.dataset.writeBoundary}`,
        { "marker-end": `url(#${step.id}-output-head)` }) });
    step.querySelector(".data-lineage-arrow").toggleAttribute("data-feature-links", inputs.length > 0 || !!boundary);
    if (!inputs.length) return updateLinks();
    inputs.forEach(input => links.push({ ...input, node,
      ...addLink(layer, "input", `Input: ${input.cell.dataset.column}`,
        { "marker-end": `url(#${step.id}-input-head)` }) }));
    mainTable.querySelectorAll('thead th[data-role="Output"]').forEach(cell => links.push({
      cell, table: mainTable, edge: "bottom", node,
      ...addLink(layer, "output", `Output: ${cell.dataset.column}`,
        { "marker-end": `url(#${step.id}-output-head)` }),
    }));
    updateLinks();
  }
  function edgeElement(table) {
    return table === mainTable && minimap.isConnected && !minimap.hidden ? minimap : table;
  }
  function curve(from, to, fromTangent, toTangent, bend) {
    return `M ${from.x} ${from.y} C ${from.x + fromTangent.x * bend} ${from.y + fromTangent.y * bend}, `
      + `${to.x + toTangent.x * bend} ${to.y + toTangent.y * bend}, ${to.x} ${to.y}`;
  }
  function updateLinks() {
    links.forEach(link => {
      const origin = link.layer.getBoundingClientRect();
      if (link.kind === "join") {
        // Joined keys are tied from the foreign table to the matching main-table dimension.
        const from = linkPoint(link.header, link.source, link.source.parentElement, origin, "top");
        const to = linkPoint(link.target, edgeElement(mainTable), mainTable.parentElement, origin, "bottom");
        link.path.setAttribute("d", curve(from, to, { x: 0, y: -1 }, { x: 0, y: 1 },
          Math.max(24, (from.y - to.y) / 2)));
        link.start.setAttribute("cx", from.x);
        link.start.setAttribute("cy", from.y);
        link.end.setAttribute("cx", to.x);
        link.end.setAttribute("cy", to.y);
        link.group.classList.toggle("is-offscreen", from.clipped || to.clipped);
        return;
      }
      if (link.kind === "write") {
        // The written table leaves through the function node into the write destination.
        const visible = !link.boundary.hidden;
        if (visible && link.group.style.display === "none" && playing) link.group.classList.add("is-new");
        link.group.style.display = visible ? "" : "none";
        if (!visible) return link.group.classList.remove("is-new");
        const box = link.boundary.getBoundingClientRect();
        const target = { x: box.left + box.width / 2 - origin.left, y: box.top - origin.top - NODE_GAP_PX };
        const rim = nodePoint(link.node, origin, target);
        link.path.setAttribute("d", curve(rim, target, rim.normal, { x: 0, y: -1 },
          Math.max(12, (target.y - rim.y) / 2)));
        link.path.style.setProperty("--length", `${link.path.getTotalLength()}px`);
        return;
      }
      const visible = !link.cell.hidden;
      if (visible && link.group.style.display === "none" && playing) link.group.classList.add("is-new");
      link.group.style.display = visible ? "" : "none";
      if (!visible) return link.group.classList.remove("is-new");
      const column = linkPoint(link.cell, edgeElement(link.table), link.table.parentElement, origin, link.edge);
      const rim = nodePoint(link.node, origin, column);
      const tangent = { x: 0, y: link.edge === "bottom" ? 1 : -1 };
      const bend = Math.max(16, Math.abs(rim.y - column.y) / 2);
      link.path.setAttribute("d", link.kind === "input"
        ? curve(column, rim, tangent, rim.normal, bend)
        : curve(rim, column, rim.normal, tangent, bend));
      link.path.style.setProperty("--length", `${link.path.getTotalLength()}px`);
      link.group.classList.toggle("is-offscreen", column.clipped);
    });
  }
  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(() => updateLinks());
    observer.observe(mainTable);
    linkLayers.forEach((layer, step) => observer.observe(step.querySelector(".data-lineage-scene")));
  }
  window.addEventListener("resize", () => {
    if (!mainTable.isConnected) return;
    anchorKeys(mainTable);
    updateMinimap();
    updateLinks();
  });
  function renderBoundary(step, frame, completed, newFrame) {
    const boundary = step.querySelector("[data-write-boundary]");
    if (boundary) {
      boundary.hidden = !completed && frame?.type !== "write";
      if (newFrame && playing && frame?.type === "write") boundary.classList.add("data-lineage-new");
    }
    return boundary;
  }
  function renderControls(step, sequence) {
    stepLinks.forEach(link => {
      if (link.hash === `#${step.id}`) {
        const changed = !link.hasAttribute("aria-current");
        link.setAttribute("aria-current", "step");
        const list = link.closest(".animation-steps");
        if (changed && list.clientHeight > 0) {
          const offset = link.getBoundingClientRect().top - list.getBoundingClientRect().top;
          if (offset < 0 || offset + link.offsetHeight > list.clientHeight) {
            list.scrollTop += offset - (list.clientHeight - link.offsetHeight) / 2;
          }
        }
      } else link.removeAttribute("aria-current");
    });
    previous.disabled = index === 0;
    next.disabled = index === steps.length - 1;
    play.textContent = playing
      ? "Pause"
      : index === steps.length - 1 && phase > sequence.length ? "Replay" : "Play";
    play.setAttribute("aria-pressed", String(playing));
  }
  function render() {
    allSteps.forEach(step => { step.hidden = step !== steps[index]; });
    stages.forEach(stage => { stage.hidden = !stage.contains(steps[index]); });
    datasetPrompt.hidden = steps.length > 0;
    previous.disabled = next.disabled = play.disabled = steps.length === 0;
    if (!steps.length) {
      stepLinks.forEach(link => link.removeAttribute("aria-current"));
      return;
    }
    const step = steps[index];
    const sequence = frames();
    const frame = sequence[phase - 1];
    const newFrame = renderedFrame !== `${index}:${phase}`;
    renderedFrame = `${index}:${phase}`;
    step.classList.toggle("is-playing", playing);
    if (newFrame) step.querySelectorAll(".data-lineage-new")
      .forEach(element => element.classList.remove("data-lineage-new"));
    const completed = phase > sequence.length;
    renderInput(step, completed);
    const arrow = step.querySelector(".data-lineage-arrow");
    arrow.classList.toggle("is-working", phase > 0 && !completed);
    if (newFrame && playing && frame?.type === "invocation") arrow.classList.add("data-lineage-new");
    const source = step.querySelector(".data-lineage-panel .data-lineage-boundary");
    if (source) source.classList.toggle("is-working", phase > 0 && !completed);
    const table = renderOutputTable(step, sequence, completed);
    if (table && newFrame) followCamera(table, frame, completed, anchorKeys(table));
    updateMinimap();
    const layer = linkLayers.get(step);
    layer.classList.toggle("is-working", phase > 0 && !completed);
    if (newFrame) layer.classList.toggle("is-drawing", playing && frame?.type === "inputs");
    const boundary = renderBoundary(step, frame, completed, newFrame);
    updateLinks();
    step.querySelector(".data-lineage-waiting").hidden = completed
      || (table ? !table.hidden : boundary ? !boundary.hidden : true);
    renderControls(step, sequence);
  }
  function pause() {
    playing = false;
    window.clearTimeout(timer);
    timer = null;
    render();
  }
  function schedule() {
    window.clearTimeout(timer);
    if (!playing) return;
    timer = window.setTimeout(() => {
      const length = frames().length;
      if (phase <= length) {
        phase += 1;
      } else if (index < steps.length - 1) {
        index += 1;
        phase = 0;
      } else {
        pause();
        return;
      }
      render();
      schedule();
    }, reducedMotion.matches ? REDUCED_MOTION_PLAYBACK_INTERVAL_MS : PLAYBACK_INTERVAL_MS);
  }
  function show(number) {
    pause();
    index = number;
    phase = frames().length + 1;
    render();
  }
  function chooseDataset(value) {
    pause();
    datasetPicker.value = value;
    const group = datasetGroups.find(item => item.dataset.animationDataset === value);
    const ids = new Set(group ? Array.from(group.querySelectorAll("a"), link => link.hash) : []);
    steps = allSteps.filter(step => ids.has(`#${step.id}`));
    datasetGroups.forEach(item => { item.hidden = item !== group; });
    index = 0;
    phase = 0;
    renderedFrame = "";
    render();
  }
  function selectStep(id) {
    const link = stepLinks.find(item => item.hash === id);
    if (!link) return;
    const value = link.closest("[data-animation-dataset]").dataset.animationDataset;
    if (datasetPicker.value !== value) chooseDataset(value);
    show(steps.findIndex(step => `#${step.id}` === id));
  }
  datasetPicker.addEventListener("change", () => {
    chooseDataset(datasetPicker.value);
    history.pushState(null, "", `#${steps[0].id}`);
  });
  previous.addEventListener("click", () => show(Math.max(0, index - 1)));
  next.addEventListener("click", () => show(Math.min(steps.length - 1, index + 1)));
  stepLinks.forEach(link => {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (location.hash !== link.hash) history.pushState(null, "", link.hash);
      selectStep(link.hash);
      window.scrollTo({ top: 0, behavior: "instant" });
    });
  });
  play.addEventListener("click", () => {
    if (playing) { pause(); return; }
    if (document.hidden) return;
    if (phase > frames().length) {
      if (index === steps.length - 1) index = 0;
      phase = 0;
    }
    playing = true;
    render();
    schedule();
  });
  board.addEventListener("click", event => {
    const link = event.target.closest('a[href^="#step-"]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (!stepLinks.some(item => item.hash === link.getAttribute("href"))) return;
    event.preventDefault();
    selectStep(link.getAttribute("href"));
    previous.focus({ preventScroll: true });
    if (previous.disabled) play.focus({ preventScroll: true });
  });
  function followHash() {
    if (stepLinks.some(link => link.hash === location.hash)) selectStep(location.hash);
    else chooseDataset("");
  }
  window.addEventListener("hashchange", followHash);
  window.addEventListener("popstate", followHash);
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  reducedMotion.addEventListener("change", () => { if (playing) pause(); });
  board.classList.add("data-lineage-enhanced");
  document.getElementById("data-lineage-toolbar").hidden = false;
  chooseDataset("");
  followHash();
})();
