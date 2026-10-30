const MAX_COLUMN_FRAMES = 6;
const FOLD_MIN_RUN = 12;
const GROUPING_PHASE = 2;

export function createDataLineageTables(allSteps, datasetSteps, onFold) {
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

  const folds = new Map();
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
    onFold();
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
  function frames(step) {
    const table = step.querySelector('table[data-side="output"]');
    const preparation = [{ type: "inputs" }];
    if (step.dataset.functionKind === "collapse") preparation.push({ type: "group" });
    preparation.push({ type: "invocation" });
    if (step.dataset.functionKind === "write") preparation.push({ type: "write" });
    if (!table) return preparation;
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
  function renderInput(step, completed, phase) {
    step.querySelectorAll('table[data-side="input"]').forEach(input =>
      renderInputTable(input, step, completed, phase));
    step.querySelectorAll('table[data-side="output"] [data-role="Input"]').forEach(cell =>
      cell.classList.toggle("data-lineage-input-active", phase > 0 && !completed));
  }
  function renderInputTable(input, step, completed, phase) {
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
  function renderOutputTable(step, sequence, completed, phase) {
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

  return { mainTable, buildMainTable, frames, renderInput, renderOutputTable };
}
