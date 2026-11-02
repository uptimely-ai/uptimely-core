import { contextHeader, contextToggle, escape, kindIcon } from "../rendering/shared_markup.js";

const TYPE_ICONS = {
  float: "hash", integer: "hash", numeric: "hash", string: "case-sensitive",
  datetime: "calendar-clock", date: "calendar", boolean: "toggle-left", object: "braces", array: "brackets",
};
const PLACEHOLDERS = {
  float: ["1.23", "4.56", "7.89"], numeric: ["1.23", "4.56", "7.89"], integer: ["12", "45", "78"],
  object: ["{}"], array: ["[]"], list: ["[]"],
  datetime: ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
  date: ["2024-01-01", "2024-01-02", "2024-01-03"],
};

export function placeholder(column, index, side) {
  const values = PLACEHOLDERS[column.type];
  if (values) return values[index % values.length];
  if (column.role === "Dimension") {
    const parts = column.name.split("_").filter(Boolean);
    const prefix = parts.length > 1 ? parts[0][0] + parts[1][0] : column.name.slice(0, 2);
    return `${prefix.toLowerCase()}-${index + 1}`;
  }
  return `${side === "input" ? "Value" : "Result"} ${index + 1}`;
}

export function sampleTable(columns, keys, label, side, rowCount, aggregate, dataset, joins = [], unshared = null) {
  const all = [...keys, ...columns];
  const attributes = column => `data-role="${escape(column.role)}" data-column="${escape(column.name)}"${joins.includes(column.name) ? " data-join-key" : unshared && column.role === "Dimension" ? ` data-dimension-change="${unshared}"` : ""}`;
  return `<div class="data-lineage-table-scroll" tabindex="0" role="region" aria-label="${escape(label ? `${label}: ${dataset}` : `${dataset} main`)} illustrative table">
    <table class="data-lineage-table" data-side="${side}"><thead><tr>${all.map(column =>
      `<th scope="col" ${attributes(column)} title="${escape(`${column.label || column.name} (${column.name}, ${column.type})`)}">
        <span class="data-lineage-cell">${TYPE_ICONS[column.type] ? `<i data-lucide="${TYPE_ICONS[column.type]}" class="data-lineage-type-icon" data-type="${escape(column.type)}" aria-hidden="true"></i>` : ""}
        ${escape(column.label || column.name)}${TYPE_ICONS[column.type] ? `<span class="sr-only"> (${escape(column.type)})</span>` : `<small>${escape(column.type)}</small>`}</span></th>`).join("")}</tr></thead>
      <tbody>${Array.from({ length: rowCount }, (_, row) => `<tr>${all.map(column =>
        `<td ${attributes(column)}><span class="data-lineage-cell">${escape(placeholder(column, column.role === "Dimension" && aggregate && joins.includes(column.name) ? 0 : row, side))}</span></td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
}

function animationStep(step, stage) {
  const keys = step.columns.filter(column => column.role === "Dimension");
  const inputs = step.columns.filter(column => column.role === "Input");
  const declared = step.columns.filter(column => column.role === "Declared input");
  const joins = [...new Set(step.input_tables.flatMap(table => table.join_dimensions))];
  const dataset = step.dataset ? step.dataset_label : step.entity;
  let sources;
  if (step.kind.is_source && step.kind.dataframe_input_scope === "none") {
    sources = `<div class="data-lineage-boundary"><strong>Source</strong>${escape(dataset)}</div>`;
  } else if (step.kind.is_effect) {
    sources = `<div class="data-lineage-boundary"><strong>Declared feature inputs</strong>${escape(declared.map(column => column.name).join(", ") || "None")}<p>These declarations do not establish that dataframe columns are available to the invocation.</p></div>`;
  } else if (step.input_tables.length) {
    sources = step.input_tables.map(table => sampleTable(table.columns, table.keys, "Source input", "input",
      table.row_count, step.kind.dimension_change === "remove", table.dataset_label, table.join_dimensions, "removed")).join("");
  } else if (step.kind.is_sink) {
    sources = `<div class="data-lineage-boundary" data-write-boundary="${escape(step.dataset || step.entity)}"><strong>Write destination</strong>${escape(dataset)}</div>`;
  } else {
    sources = inputs.length || keys.length ? "" : '<div class="data-lineage-boundary"><strong>No declared input columns</strong>Only declared information is shown.</div>';
  }
  return `<article class="data-lineage-step" id="step-${step.number}" data-invocation-id="${escape(step.invocation_id)}"
    data-dependencies="${escape(step.dependencies.join(","))}" data-function-kind="${escape(step.kind.id)}" data-stage="${stage}" aria-labelledby="step-${step.number}-title">
    <header class="data-lineage-step-header"><h3 id="step-${step.number}-title">${escape(step.action)}</h3>
      <p class="data-lineage-step-dataset">Dataset: ${escape(dataset)}</p></header>
    <div class="data-lineage-scene"><div class="data-lineage-panel data-lineage-panel-output">
      <p class="data-lineage-waiting" hidden>New features will appear in the main table as the action runs.</p>
      ${sampleTable(step.main_columns.filter(column => column.role !== "Existing"), keys, null, "output", step.row_count,
        ["remove", "add"].includes(step.kind.dimension_change), dataset, joins, step.input_tables.length ? "added" : null)}
    </div><div class="data-lineage-arrow" data-flow="${step.kind.is_sink ? "down" : "up"}">
      <span class="data-lineage-edge" aria-hidden="true"></span><span class="data-lineage-node icon--functions" aria-hidden="true">${kindIcon(step.kind.id, "")}</span>
      <span class="data-lineage-node-label"><small class="data-lineage-invocation-type">${escape(step.kind.id === "collapse" ? "Aggregate" : step.kind.id === "escape" ? "Uncontrolled external operation" : step.kind.id[0].toUpperCase() + step.kind.id.slice(1))}</small>
        <code title="${escape(step.function)}">${escape(step.function_label)}</code></span>
    </div><div class="data-lineage-panel data-lineage-sources">${sources}</div></div></article>`;
}

export function animation(data) {
  const stages = data.animation.stages.filter(stage => stage.length);
  const datasets = new Map(), stageNumbers = new Map();
  stages.forEach((stage, index) => stage.forEach(step => {
    stageNumbers.set(step.number, index);
    if (!datasets.has(step.dataset)) datasets.set(step.dataset, []);
    datasets.get(step.dataset).push(step);
  }));
  const groups = [...datasets.values()];
  return {
    context: `<aside class="site-context" id="animation-context" aria-label="Animation context" data-context-label="animation">
      ${contextHeader("Animation", "data-lineage", "animation-context")}
      <button class="ui-button context-close" type="button" aria-label="Close animation context">Close</button>
      ${stages.length ? `<div class="data-lineage-toolbar" id="data-lineage-toolbar" role="group" aria-label="Lineage playback" hidden>
        <button class="ui-button" type="button" id="data-lineage-previous">Previous</button>
        <button class="ui-button" type="button" id="data-lineage-play" aria-pressed="false">Play</button>
        <button class="ui-button" type="button" id="data-lineage-next">Next</button></div>
        <div class="animation-dataset-picker"><label for="animation-dataset">Dataset</label>
          <select id="animation-dataset" required><option value="" disabled selected>Choose a dataset</option>
            ${groups.map((steps, index) => `<option value="${index + 1}" title="${escape(steps[0].dataset_label)}">${escape(steps[0].dataset_label)}</option>`).join("")}</select></div>
        <nav class="context-links animation-steps" aria-label="Animation steps">${groups.map((steps, index) => {
          let previousStage = null, number = 0;
          return `<div class="context-link-group" data-animation-dataset="${index + 1}">${steps.map((step, position) => {
            const stage = stageNumbers.get(step.number), changed = stage !== previousStage;
            if (changed) number++;
            previousStage = stage;
            return `${changed ? `<p class="context-group-label animation-stage-label"><span>Stage ${number}</span></p>` : ""}
              <a href="#step-${step.number}" data-animation-step="${step.number}"><span class="animation-step-number">${position + 1}</span>
                <span class="context-link-icon" title="${escape(step.kind.id)}">${kindIcon(step.kind.id)}</span><span class="context-link-label">${escape(step.action)}</span></a>`;
          }).join("")}</div>`;
        }).join("")}</nav>` : '<p class="context-empty">No processing steps.</p>'}
    </aside>`,
    content: `<main class="data-lineage-page">${contextToggle("animation-context", "Animation")}
      ${stages.length ? `<p id="animation-dataset-prompt" role="status" hidden>Choose a dataset in Animation controls to view its actions.</p>
        <div id="data-lineage-board">${stages.map((stage, index) => `<section class="data-lineage-stage" aria-labelledby="stage-${index + 1}">
          <h2 id="stage-${index + 1}">Stage ${index + 1} / ${stage.length} independent step${stage.length === 1 ? "" : "s"}</h2>
          ${stage.map(step => animationStep(step, index + 1)).join("")}</section>`).join("")}</div>`
        : "<p>No processing steps. Add function actions to the spec to display the animation.</p>"}</main>`,
  };
}
