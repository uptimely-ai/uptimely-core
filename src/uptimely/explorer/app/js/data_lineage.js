(() => {
  const board = document.getElementById("lineage-board");
  if (!board) return;
  const steps = Array.from(board.querySelectorAll(".lineage-step"));
  const stages = Array.from(board.querySelectorAll(".lineage-stage"));
  const previous = document.getElementById("lineage-previous");
  const next = document.getElementById("lineage-next");
  const play = document.getElementById("lineage-play");
  const position = document.getElementById("lineage-position");
  const stagePosition = document.getElementById("lineage-stage-position");
  const stepMarkers = Array.from(document.querySelectorAll("[data-step-marker]"));
  const stageMarkers = Array.from(document.querySelectorAll("[data-stage-marker]"));
  const playbackProgress = document.getElementById("lineage-playback-progress");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const descriptions = steps.map(step => step.querySelector(".lineage-status").textContent);
  let index = 0;
  let phase = 0;
  let playing = false;
  let timer = null;
  let renderedFrame = "";
  function frames() {
    const step = steps[index];
    const table = step.querySelector('table[data-side="output"]');
    const preparation = [{ type: "inputs" }];
    if (step.dataset.operation === "collapse") preparation.push({ type: "group" });
    preparation.push({ type: "invocation" });
    if (!table) {
      if (step.dataset.operation === "write") preparation.push({ type: "write" });
      return preparation;
    }
    const headers = Array.from(table.querySelectorAll('thead th[data-role="Output"]'));
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    return [...preparation, ...headers.map(header => ({ type: "column", element: header })),
      ...rows.map(row => ({ type: "row", element: row }))];
  }
  function render() {
    steps.forEach((step, number) => { step.hidden = number !== index; });
    stages.forEach(stage => { stage.hidden = !stage.contains(steps[index]); });
    const step = steps[index];
    const sequence = frames();
    const frame = sequence[phase - 1];
    const newFrame = renderedFrame !== `${index}:${phase}`;
    renderedFrame = `${index}:${phase}`;
    step.classList.toggle("is-playing", playing);
    if (newFrame) step.querySelectorAll(".lineage-new").forEach(element => element.classList.remove("lineage-new"));
    const completed = phase > sequence.length;
    const input = step.querySelector('table[data-side="input"]');
    if (input) {
      input.classList.toggle("lineage-grouped", phase >= 2 && step.dataset.operation === "collapse" && !completed);
      input.querySelectorAll("[data-role]").forEach(cell => {
        cell.classList.toggle("lineage-input-active", phase > 0 && !completed && cell.dataset.role === "Input");
        cell.classList.toggle("lineage-group-key", phase >= 2 && !completed
          && step.dataset.operation === "collapse" && cell.dataset.role === "Dimension");
      });
    }
    const arrow = step.querySelector(".lineage-arrow");
    arrow.classList.toggle("is-working", phase > 0 && !completed);
    if (newFrame && playing && frame?.type === "invocation") arrow.classList.add("lineage-new");
    const source = step.querySelector(".lineage-panel .lineage-boundary");
    if (source) source.classList.toggle("is-working", phase > 0 && !completed);
    const table = step.querySelector('table[data-side="output"]');
    if (table) {
      const visibleColumns = new Set(sequence.slice(0, phase)
        .filter(frame => frame.type === "column").map(frame => frame.element.cellIndex));
      table.querySelectorAll("tr").forEach(row => {
        Array.from(row.cells).forEach((cell, column) => {
          cell.hidden = cell.dataset.role === "Output" && !visibleColumns.has(column);
        });
      });
      const visibleRows = new Set(sequence.slice(0, phase)
        .filter(frame => frame.type === "row").map(frame => frame.element));
      table.querySelectorAll("tbody tr").forEach(row => {
        row.hidden = !visibleRows.has(row);
      });
      table.hidden = !completed && !sequence.slice(0, phase).some(frame => frame.type === "column" || frame.type === "row");
      table.parentElement.hidden = table.hidden;
    }
    const boundary = step.querySelector("[data-write-boundary]");
    if (boundary) {
      boundary.hidden = !completed && frame?.type !== "write";
      if (newFrame && playing && frame?.type === "write") boundary.classList.add("lineage-new");
    }
    step.querySelector(".lineage-waiting").hidden = completed
      || (table ? !table.hidden : boundary ? !boundary.hidden : true);
    const status = step.querySelector(".lineage-status");
    if (phase === 0) {
      status.textContent = "Input ready. Play to illustrate the invocation.";
    } else if (phase > sequence.length) {
      status.textContent = descriptions[index];
    } else {
      if (frame.type === "inputs") {
        status.textContent = step.dataset.operation === "escape"
          ? "Showing declared feature references; dataframe column availability is not verified."
          : step.dataset.operation === "read"
          ? "Reading from the declared source (illustration only)."
          : "Highlighting all declared input columns. Exact input-to-output mappings are not inferred.";
      } else if (frame.type === "group") {
        status.textContent = "Grouping the three placeholder rows by their shared keys (one illustrative group).";
      } else if (frame.type === "invocation") {
        status.textContent = `Illustrating ${step.querySelector("h3").textContent}. The function is not executed.`;
      } else if (frame.type === "write") {
        status.textContent = "Passing the illustrative input table to the write destination. No new analytical columns.";
      } else if (frame.type === "column") {
        status.textContent = `Adding declared column: ${frame.element.dataset.column}`;
        if (playing && newFrame) {
          const column = frame.element.cellIndex;
          table.querySelectorAll("tr").forEach(row => row.cells[column].classList.add("lineage-new"));
        }
      } else {
        status.textContent = "Adding an illustrative row (not calculated data).";
        if (playing && newFrame) frame.element.classList.add("lineage-new");
      }
    }
    previous.disabled = index === 0;
    next.disabled = index === steps.length - 1;
    position.value = `Step ${index + 1} of ${steps.length}`;
    stagePosition.value = `Stage ${step.dataset.stage} of ${stages.length}`;
    stageMarkers.forEach(marker => {
      const markerStage = Number(marker.dataset.stageMarker);
      marker.classList.toggle("is-current", markerStage === Number(step.dataset.stage));
      marker.classList.toggle("is-complete", markerStage < Number(step.dataset.stage));
    });
    stepMarkers.forEach(marker => {
      const markerStep = Number(marker.dataset.stepMarker);
      marker.classList.toggle("is-current", markerStep === index + 1);
      marker.classList.toggle("is-complete", markerStep < index + 1);
    });
    play.textContent = playing ? "Pause" : index === steps.length - 1 && phase > sequence.length ? "Replay" : "Play";
    play.setAttribute("aria-pressed", String(playing));
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
    }, reducedMotion.matches ? 1800 : 1200);
  }
  function show(number) {
    pause();
    index = number;
    phase = frames().length + 1;
    render();
  }
  previous.addEventListener("click", () => show(Math.max(0, index - 1)));
  next.addEventListener("click", () => show(Math.min(steps.length - 1, index + 1)));
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
    const number = steps.findIndex(step => `#${step.id}` === link.getAttribute("href"));
    if (number < 0) return;
    event.preventDefault();
    show(number);
    previous.focus({ preventScroll: true });
    if (previous.disabled) play.focus({ preventScroll: true });
  });
  function followHash() {
    const number = steps.findIndex(step => `#${step.id}` === location.hash);
    if (number >= 0) show(number);
  }
  window.addEventListener("hashchange", followHash);
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  reducedMotion.addEventListener("change", () => { if (playing) pause(); });
  board.classList.add("lineage-enhanced");
  document.getElementById("lineage-toolbar").hidden = false;
  playbackProgress.hidden = false;
  render();
  followHash();
})();
