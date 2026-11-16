# Dimensions, resolutions and grain

## Grain

<p class="cv-function-subtitle">Available observation keys and their levels</p>

A **dimension** describes an observation axis, such as a machine or time. Its
**resolutions** declare the available keys and form a hierarchy. Each resolution
can name a coarser parent, so the root is the coarsest level and its children are
finer. A profile's grain selects one resolution per dimension.

P-01 is one key of the `machine` resolution. Differential pressure and flow
are measured cooling-pump features, not dimensions.

<div class="concepts-visual">
  <div class="cv-grain-hierarchies">
    <section class="cv-grain-dimension" aria-label="Cooling pump dimension">
      <span class="cv-tag">DIMENSION / machine_dimension</span>
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
      <span class="cv-tag">DIMENSION / machine_timestamp</span>
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
