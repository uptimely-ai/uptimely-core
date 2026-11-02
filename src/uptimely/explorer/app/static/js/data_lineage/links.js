const LINK_INSET_PX = 10;
const NODE_GAP_PX = 4;
const NODE_LABEL_SIDE = 0.5;
const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

export function createDataLineageLinks(
  allSteps, mainTable, viewport, isPlaying,
) {
  const { minimap, anchorKeys, updateMinimap } = viewport;
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
        if (visible && link.group.style.display === "none" && isPlaying()) link.group.classList.add("is-new");
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
      if (visible && link.group.style.display === "none" && isPlaying()) link.group.classList.add("is-new");
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

  allSteps.forEach(step => {
    step.querySelector(".data-lineage-panel-output .data-lineage-table-scroll")
      .addEventListener("scroll", updateLinks, { passive: true });
    step.querySelectorAll(".data-lineage-sources .data-lineage-table-scroll")
      .forEach(source => source.addEventListener("scroll", updateLinks, { passive: true }));
  });
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

  return { buildLinks, updateLinks, layerFor: step => linkLayers.get(step) };
}
