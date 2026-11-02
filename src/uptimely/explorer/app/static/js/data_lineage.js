import { createDataLineageLinks } from "./data_lineage/links.js";
import { createDataLineageTables } from "./data_lineage/tables.js";
import { createDataLineageViewport } from "./data_lineage/viewport.js";

function initializeDataLineage() {
  const PLAYBACK_INTERVAL_MS = 1200;
  const REDUCED_MOTION_PLAYBACK_INTERVAL_MS = 1800;
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
  const datasetPicker = document.getElementById("animation-dataset");
  const datasetGroups = Array.from(document.querySelectorAll("[data-animation-dataset]"));
  const datasetSteps = new Map();
  datasetGroups.forEach(group => {
    const ordered = Array.from(group.querySelectorAll("[data-animation-step]"),
      link => document.getElementById(link.hash.slice(1)));
    ordered.forEach(step => datasetSteps.set(step, ordered));
  });
  const datasetPrompt = document.getElementById("animation-dataset-prompt");
  let index = 0;
  let phase = 0;
  let playing = false;
  let timer = null;
  let renderedFrame = "";
  let mainStep = null;
  const tables = createDataLineageTables(allSteps, datasetSteps, refreshMainTable);
  const mainTable = tables.mainTable;
  const viewport = createDataLineageViewport(
    allSteps, mainTable, reducedMotion, () => playing,
  );
  const lineageLinks = createDataLineageLinks(
    allSteps, mainTable, viewport, () => playing,
  );

  function refreshMainTable() {
    viewport.anchorKeys(tables.mainTable);
    viewport.updateMinimap();
    lineageLinks.updateLinks();
  }

  function frames() {
    const step = steps[index];
    if (mainStep !== step) {
      tables.buildMainTable(step);
      const tableViewport = step.querySelector(".data-lineage-panel-output .data-lineage-table-scroll");
      tableViewport.append(mainTable);
      tableViewport.after(viewport.minimap);
      tableViewport.scrollLeft = 0;
      mainStep = step;
      lineageLinks.buildLinks(step);
    }
    return tables.frames(step);
  }
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
    tables.renderInput(step, completed, phase);
    const arrow = step.querySelector(".data-lineage-arrow");
    arrow.classList.toggle("is-working", phase > 0 && !completed);
    if (newFrame && playing && frame?.type === "invocation") arrow.classList.add("data-lineage-new");
    const source = step.querySelector(".data-lineage-panel .data-lineage-boundary");
    if (source) source.classList.toggle("is-working", phase > 0 && !completed);
    const table = tables.renderOutputTable(step, sequence, completed, phase);
    if (table && newFrame) {
      viewport.followCamera(table, frame, completed, viewport.anchorKeys(table), phase);
    }
    viewport.updateMinimap();
    const layer = lineageLinks.layerFor(step);
    layer.classList.toggle("is-working", phase > 0 && !completed);
    if (newFrame) layer.classList.toggle("is-drawing", playing && frame?.type === "inputs");
    const boundary = renderBoundary(step, frame, completed, newFrame);
    lineageLinks.updateLinks();
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
}

initializeDataLineage();
