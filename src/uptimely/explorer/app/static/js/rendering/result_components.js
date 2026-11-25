import { escape, formatTimestamp } from "./shared_markup.js";

export function outcomeSummary(title, totalLabel, total, counts, statuses, description) {
  return `<section class="engine-outcome-group" aria-label="${escape(title)}">
    <h2 class="ui-section-title">Summary</h2>
    <div class="engine-outcome-summary">
      <div class="engine-outcome-total"><span>${escape(totalLabel)}</span><strong>${total}</strong></div>
      <div class="engine-outcome-progress" role="img" aria-label="${escape(description)}">
        ${statuses.filter(([status]) => (counts[status] || 0) > 0).map(([status]) =>
          `<span class="engine-outcome-progress-${escape(status)}" style="flex-grow:${counts[status]}"></span>`).join("")}
      </div>
      <ul class="engine-outcome-legend">${statuses.map(([status, label]) => `<li>
        <span class="engine-outcome-legend-label"><i class="engine-outcome-legend-${escape(status)}" aria-hidden="true"></i>${escape(label)}</span>
        <strong>${counts[status] || 0}</strong>
      </li>`).join("")}</ul>
    </div>
  </section>`;
}

export function timingTimeline(title, startedAt, duration, finishedAt) {
  const timestamp = value => value
    ? `<time datetime="${escape(value)}">${escape(formatTimestamp(value))}</time>` : "<span>—</span>";
  return `<section class="engine-timing">
    <h2 class="ui-section-title">Timeline</h2>
    <div class="engine-timeline" role="group" aria-label="${escape(title)}">
      <div class="engine-timeline-event">
        <span class="engine-timeline-label">Started</span>${timestamp(startedAt)}
      </div>
      <div class="engine-timeline-duration">
        <span>Duration</span><strong>${escape(duration)}</strong>
      </div>
      <div class="engine-timeline-event">
        <span class="engine-timeline-label">Finished</span>${timestamp(finishedAt)}
      </div>
    </div>
  </section>`;
}
