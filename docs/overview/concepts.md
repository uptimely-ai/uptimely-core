# Concepts

The examples below use pump measurements to show how dimensions, resolutions,
profiles, features, function contracts, and operators describe an analytical system.

## Grain

<p class="cv-function-subtitle">Available observation keys and their levels</p>

A **dimension** describes an observation axis, such as a machine or time. Its
**resolutions** declare the available keys and form a hierarchy. Each resolution
can name a coarser parent, so the root is the coarsest level and its children are
finer. A profile's grain selects one resolution per dimension.

P-01 is one key of the `machine` resolution. Pressure and flow are measured
features, not dimensions.

<div class="concepts-visual">
  <div class="cv-grain-hierarchies">
    <section class="cv-grain-dimension" aria-label="Machine dimension">
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
  <p class="cv-detail">Highlighted resolutions form the grain of the telemetry profile below: one pump at one timestamp.</p>
</div>

## Profile

<p class="cv-function-subtitle">A selected grain and its available features</p>

A profile is more than data. It is an analytical specification with three parts:

- A **scope** that describes what the profile covers.
- A set of **analytical operators** that produce and transform its features.
- A **unique set of features**. Each feature belongs to exactly one profile and has exactly one producing operator.

A profile selects one resolution per dimension in its ordered `grain`. This
profile selects pump and timestamp keys for minute-by-minute observations.

Other profiles could represent:

| Profile | What one row represents | Example features |
| --- | --- | --- |
| Pump reference data | One pump | Rated flow, installation date |
| Minute-level telemetry | One pump at one timestamp | Pressure, flow |
| Daily pump summaries | One pump on one day | Maximum pressure, average flow |
| Maintenance events | One maintenance event for a pump | Event type, downtime |

Note that this is analytical representation.
Data might be stored physically in different way.

<div class="concepts-visual">
  <div class="cv-profile">
    <div class="cv-scope">
      <div><span>GRAIN</span><strong>One pump at one timestamp</strong></div>
      <div><span>SCOPE / DESCRIPTIVE ONLY</span><strong>Pump telemetry observations</strong></div>
      <div><span>CATEGORY</span><strong>Telemetry</strong></div>
    </div>
    <div class="cv-table-scroll">
      <table class="cv-table cv-model-table">
        <thead>
          <tr class="cv-bands"><th colspan="2" class="cv-key">DIMENSIONS / observation keys</th><th colspan="2" class="cv-teal">TELEMETRY / operator A</th><th class="cv-violet">LIMITS / operator B</th><th class="cv-amber">CALCULATED</th></tr>
          <tr><th class="cv-key">pump</th><th class="cv-key">timestamp</th><th class="cv-teal">pressure</th><th class="cv-teal">flow</th><th class="cv-violet">limit</th><th class="cv-amber">ratio</th></tr>
        </thead>
        <tbody>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-teal">12</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-teal">14</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-teal">10</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr>
        </tbody>
      </table>
    </div>
    <p class="cv-legend-title">Color key</p>
    <ul class="cv-legend-row">
      <li><span class="cv-swatch cv-key" aria-hidden="true"></span>Dimension keys</li>
      <li><span class="cv-swatch cv-teal" aria-hidden="true"></span>Telemetry features</li>
      <li><span class="cv-swatch cv-violet" aria-hidden="true"></span>Limit features</li>
      <li><span class="cv-swatch cv-amber" aria-hidden="true"></span>Calculated features</li>
    </ul>
  </div>
</div>

The combined profile dataframe is a conceptual view, not a requirement to store all
intermediate columns in one physical table.

## Function contracts

A **function** is reusable code with typed arguments and a declared return
contract. An operator uses a function in one of two binding roles. Each role
accepts a fixed number of dataframe arguments and returns a dataframe or nothing.

<div class="concepts-visual">
  <div class="cv-contracts" role="group" aria-label="Function contracts by dataframe inputs and outputs">
    <div class="cv-contract">
      <span class="cv-tag">COMPUTE 0&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">no input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Produces data from outside the spec, such as a source read.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">COMPUTE 1&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Transforms a dataframe into a new dataframe or fragment.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">COMPUTE 1&#8594;0</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">no output</span></div></div>
      <p>Consumes a dataframe for a side effect, such as a write.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">COMPUTE any&#8594;any</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">any input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">ignored</span></div></div>
      <p>Runs an opaque external workflow and ignores its result.</p>
    </div>
    <div class="cv-contract cv-contract-merge">
      <span class="cv-tag">MERGE 2&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataset</span><span class="cv-slot">fragment</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Combines the current dataset with a staged fragment.</p>
    </div>
  </div>
</div>

<div class="concepts-visual">
  <div class="cv-label-note">
    <span class="cv-label-badge"><small>inferred label</small>vectorize</span>
    <p>Badges mark <strong>inferred operator labels</strong>. You never declare them. Uptimely derives each one from the operator's contract and grain, so the same function can get different labels in different operators.</p>
  </div>
</div>

### Compute 0→1

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>read</span></p>

<p class="cv-function-subtitle">No input dataframe, brings data in from a source</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div class="cv-endpoint"><span class="cv-endpoint-icon" aria-hidden="true">&#8645;</span><strong>Telemetry source</strong><span>Database or file</span><code>pump = P-01<br/>09:00 through 09:02</code></div>
      <div class="cv-arrow"><span>retrieve</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">OUTPUT / 3 observations</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
    </div>
  </div>
</div>

### Compute 1→1

The function receives one dataframe and returns a dataframe. The result is
either the complete target or a fragment that a merge combines with the current
dataset. The target grain relative to the input produces the derived labels
below.

#### Vectorize

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>vectorize</span></p>

<p class="cv-function-subtitle">Same profile as input, adds features and keeps rows</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">BEFORE / input features</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>divide</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">AFTER / one new feature</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-amber">0.50</td></tr></tbody></table></div>
    </div>
  </div>
</div>

#### Conform

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>conform</span></p>

<p class="cv-function-subtitle">Keeps dimensions, aligns resolution</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE / wider time selection</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr class="cv-muted-row"><td class="cv-key">P-01</td><td class="cv-key">08:59</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>align</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET / telemetry keys</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
    </div>
  </div>
</div>

#### Expand

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>expand</span></p>

<p class="cv-function-subtitle">Adds dimensions to the input grain</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE PROFILE / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-violet">8</td></tr></tbody></table><p class="cv-detail">One value for the pump.</p></div>
      <div class="cv-arrow"><span>extend</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET FRAGMENT / pump + time</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
    </div>
  </div>
</div>

#### Collapse

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>collapse</span></p>

<p class="cv-function-subtitle">Collapses finer input grain to a coarser grain</p>

`collapse` describes an operator whose source grain is finer than its target
grain. Its compute implementation performs grouping and returns results at the
target grain; this label is derived from the declarations, not attached to
the callable.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE / pump + time grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>collapse</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-amber">max_pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-amber">8</td></tr></tbody></table><p class="cv-detail">One row summarizes the three moments.</p></div>
    </div>
  </div>
</div>

### Compute 1→0

The function receives one dataframe and returns nothing, so it declares no
materialized features.

#### Write

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>write</span></p>

<p class="cv-function-subtitle">Takes the input dataframe and returns nothing</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">INPUT / selected features</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-amber">0.50</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>deliver</span><b aria-hidden="true">&#8594;</b></div>
      <div class="cv-endpoint"><span class="cv-endpoint-icon" aria-hidden="true">&#8599;</span><strong>Your destination</strong><span>Persist to a database or file.<br/>Print a report.<br/>Evaluate the results.</span></div>
    </div>
  </div>
</div>

### Compute any→any

The function accepts any arguments and its result is ignored (`returns="any"`). Declared features act as logical dependencies and are not materialized as dataframe columns.

#### Escape

<p class="cv-label-line"><span class="cv-label-badge"><small>inferred label</small>escape</span></p>

<p class="cv-function-subtitle">Result is ignored, no dataframe output</p>

Use `returns="any"` when an external workflow's result must be ignored. Prefer
explicit dataframe dataflow and runtime checks when they fit the work.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-endpoint">
      <span class="cv-tag">ESCAPE / ONE FUNCTION</span>
      <strong>External workflow</strong>
      <span>Read source <span aria-hidden="true">&rarr;</span> calculate <span aria-hidden="true">&rarr;</span> write result</span>
    </div>
  </div>
</div>

### Merge 2→1

<p class="cv-function-subtitle">Combine the current dataset with a staged fragment</p>

When an operator declares a merge, its compute step returns a fragment instead
of the complete target. Fragment is data transformed to fit to target profiles,grain. The merge receives the current dataset, which is empty
for the first operator, and that fragment. It returns the updated dataset.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">DATASET + FRAGMENT / two inputs</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr></tbody></table><table class="cv-table cv-stacked"><thead><tr><th class="cv-key">time</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-amber">1.00</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>merge</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">DATASET / one output</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-amber">1.00</td></tr></tbody></table></div>
    </div>
    <p class="cv-takeaway"><strong>Merge bindings take exactly two dataframes and return one.</strong> The builtin merge aligns the fragment to the dataset by grain.</p>
  </div>
</div>

## Operator

<p class="cv-function-subtitle">Connect feature dependencies and outputs to a function binding</p>

An operator declares which features a function needs and produces, then binds
that function to concrete arguments. In this example, `divide` receives the
current profile dataframe and feature identifiers, and returns `pressure_ratio`.

<div class="concepts-visual">
  <div class="cv-operation cv-mapping-flow" role="group" aria-label="Input dataframe, Python operator, and output dataframe">
    <div class="cv-mapping-stage cv-mapping-inputs">
      <span class="cv-tag">INPUT DATAFRAME / declared features</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td></tr></tbody></table>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-call">
      <span class="cv-tag">OPERATOR / PYTHON</span>
      <pre class="cv-mapping-code"><code>up.Operator(
    id=<span class="cv-amber">"pressure_ratio"</span>,
    <span class="cv-violet">interface</span>=up.Interface(
        <span class="cv-teal">inputs</span>=[
            up.ref.feature(<span class="cv-teal">"pressure"</span>),
            up.ref.feature(<span class="cv-violet">"limit"</span>),
        ],
        <span class="cv-teal">outputs</span>=[up.Feature(id=<span class="cv-amber">"pressure_ratio"</span>)],
    ),
    <span class="cv-teal">compute</span>=up.Binding(
        <span class="cv-teal">function</span>=<span class="cv-amber">divide</span>,
        <span class="cv-teal">arguments</span>={
            <span class="cv-teal">"dataset"</span>: up.ref.dataset(),
            <span class="cv-teal">"numerator"</span>: up.ref.feature(<span class="cv-teal">"pressure"</span>).id,
            <span class="cv-teal">"denominator"</span>: up.ref.feature(<span class="cv-violet">"limit"</span>).id,
            <span class="cv-teal">"output"</span>: up.ref.feature(<span class="cv-amber">"pressure_ratio"</span>).id,
        },
    ),
)</code></pre>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-outputs">
      <span class="cv-tag">OUTPUT DATAFRAME / declared feature</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th><th class="cv-amber">pressure_ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr></tbody></table>
    </div>
    <p class="cv-takeaway"><strong>Two complementary declarations.</strong> Feature inputs and outputs describe data dependencies. Compute arguments provide the dataframe and feature identifiers the function uses; an identifier argument alone does not declare an input dependency.</p>
  </div>
</div>
