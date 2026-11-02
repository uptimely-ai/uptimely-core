const ANCHOR_MAX_SHARE = 0.5;
const CAMERA_MARGIN_PX = 24;
const CAMERA_CUT_VIEWPORTS = 2;

export function createDataLineageViewport(allSteps, mainTable, reducedMotion, isPlaying) {
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

  function columnBounds(viewport, cell) {
    const left = cell.getBoundingClientRect().left - viewport.getBoundingClientRect().left
      + viewport.scrollLeft;
    return { left, right: left + cell.offsetWidth };
  }
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
  function cameraTargets(table, frame, completed, phase) {
    if (frame?.type === "column") return frame.elements;
    const active = Array.from(table.querySelectorAll("thead th.data-lineage-input-active"));
    if (phase > 0 && !completed && active.length) return active;
    const outputs = Array.from(table.querySelectorAll('thead th[data-role="Output"]'))
      .filter(cell => !cell.hidden);
    return outputs.length ? outputs : Array.from(table.querySelectorAll('thead th[data-role="Input"]'));
  }
  function followCamera(table, frame, completed, anchorWidth, phase) {
    const viewport = table.parentElement;
    const targets = cameraTargets(table, frame, completed, phase);
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
    const near = Math.abs(target - viewport.scrollLeft) <= viewport.clientWidth * CAMERA_CUT_VIEWPORTS;
    viewport.scrollTo({
      left: target,
      behavior: isPlaying() && near && !reducedMotion.matches ? "smooth" : "instant",
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
  let grab = null;
  function minimapShare(event) {
    const bounds = minimap.getBoundingClientRect();
    return (event.clientX - bounds.left) / bounds.width;
  }
  function pan(left, glide) {
    mainTable.parentElement.scrollTo({
      left, behavior: glide && !reducedMotion.matches ? "smooth" : "instant",
    });
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
  });

  return { minimap, anchorKeys, followCamera, updateMinimap };
}
