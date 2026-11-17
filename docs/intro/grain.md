# Dimensions, resolutions and grain

## Dimension

A **dimension** describes an observation axis, such as a machine or time.

## Resolution

Dimensions consist of one or more resolutions. If there are more than one resolutions, the form a hierarchy. For example timestamp -> hour -> day.

The resolutions are used as identifiers in Uptimely framework.

## Grain

Grain is a combination of resolutions that are describe an entity (profile in Uptimely terms). Grain can only contain one resolution per dimension.

Resolutions that define granularity are each called identifiers. Resolutions that point to other profile are known as relations. Together identifiers and relations are called keys.

## Visualization of grain, dimension and resolution

Below is visualization of grain with machine and time dimension. This combination could be described simply as "machine telemetry".

There could be other grain using machine series and day resolution. That could be described as "machine series daily summary".

<div class="concepts-visual">
  <div class="cv-grain-hierarchies">
    <section class="cv-grain-dimension" aria-label="Cooling pump dimension">
      <span class="cv-tag">Machine dimension</span>
      <ul class="cv-res-tree" aria-label="Resolution hierarchy">
        <li>
          <div class="cv-res-card"><strong>machine_category</strong><span>machine_category_id</span></div>
          <ul class="cv-res-children">
            <li>
              <div class="cv-res-card"><strong>machine_series</strong><span>machine_series_id</span></div>
              <ul class="cv-res-children">
                <li><div class="cv-res-card cv-res-selected"><strong>machine</strong><span>pump_id / P-01</span></div></li>
              </ul>
            </li>
          </ul>
        </li>
      </ul>
    </section>
    <section class="cv-grain-dimension" aria-label="Time dimension">
      <span class="cv-tag">Time dimension</span>
      <ul class="cv-res-tree" aria-label="Resolution hierarchy">
        <li>
          <div class="cv-res-card"><strong>day</strong><span>day</span></div>
          <ul class="cv-res-children">
            <li>
              <div class="cv-res-card"><strong>hour</strong><span>hour</span></div>
              <ul class="cv-res-children">
                <li>
                  <div class="cv-res-card"><strong>minute</strong><span>minute</span></div>
                  <ul class="cv-res-children">
                    <li><div class="cv-res-card cv-res-selected"><strong>timestamp</strong><span>timestamp / 09:00</span></div></li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </li>
      </ul>
    </section>
  </div>
  <p class="cv-detail">Highlighted resolutions form the grain of the telemetry profile below: one cooling pump at one timestamp.</p>
</div>
