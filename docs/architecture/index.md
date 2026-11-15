# Architecture

Uptimely has five core components: App, Spec, Compiler, Engine, and
Explorer. The Spec describes an analytical system. The App builds a portable
bundle containing the Spec and an execution plan resolved by the Compiler.
The Engine executes the plan, and the Explorer presents build and run
information for inspection.

## Workflow

The build produces a bundle for execution and a separate Explorer snapshot.
The Engine uses the bundle with runtime configuration and importable functions.
Explorer can inspect the build without running the Engine.

<div class="concepts-visual architecture-visual">
  <div class="av-journey">
    <section class="av-phase" aria-labelledby="av-build">
      <h3 id="av-build">Build</h3>
      <div class="av-flow">
        <div class="av-node av-definition">
          <span class="av-node-label">SOURCE</span>
          <strong>Spec</strong>
          <span>Python definition or JSON document</span>
        </div>
        <div class="av-connector" aria-hidden="true">&#8594;</div>
        <div class="av-node av-operator">
          <span class="av-node-label">PROJECT BUILDER</span>
          <strong>Load and compile</strong>
          <span>Compiler validates the Spec and resolves an execution plan</span>
        </div>
        <div class="av-connector" aria-hidden="true">&#8594;</div>
        <div class="av-node av-definition">
          <span class="av-node-label">OUTPUTS</span>
          <strong>Build bundle and Explorer snapshot</strong>
          <span>Bundle contains the Spec, plan, and manifest</span>
        </div>
      </div>
    </section>
    <section class="av-phase" aria-labelledby="av-run">
      <h3 id="av-run">Execute</h3>
      <div class="av-flow">
        <div class="av-node av-definition">
          <span class="av-node-label">INPUTS</span>
          <strong>Build bundle and runtime configuration</strong>
          <span>Configuration supplies paths, parameters, and backend settings</span>
        </div>
        <div class="av-connector" aria-hidden="true">&#8594;</div>
        <div class="av-node av-operator">
          <span class="av-node-label">ENGINE</span>
          <strong>Execute invocations</strong>
          <span>Calls importable functions in dependency order</span>
        </div>
        <div class="av-connector" aria-hidden="true">&#8594;</div>
        <div class="av-node av-result">
          <span class="av-node-label">OUTPUTS</span>
          <strong>Execution result and run snapshot</strong>
          <span>Dataframes, statuses, logs, and previews</span>
        </div>
      </div>
    </section>
    <section class="av-phase" aria-labelledby="av-inspect">
      <h3 id="av-inspect">Inspect</h3>
      <div class="av-flow">
        <div class="av-node av-definition">
          <span class="av-node-label">INPUTS</span>
          <strong>Explorer snapshot and optional run snapshot</strong>
          <span>Build data is available before execution</span>
        </div>
        <div class="av-connector" aria-hidden="true">&#8594;</div>
        <div class="av-node av-result">
          <span class="av-node-label">EXPLORER</span>
          <strong>Present project data</strong>
          <span>Displays the Spec, lineage, plan, and available run details</span>
        </div>
      </div>
    </section>
  </div>
</div>

The [App](application.md) coordinates the build and publishes the outputs.
See the [Compiler](compiler.md), [Execution plan](execution-plan.md),
[Engine](engine.md), and [Explorer](explorer.md) pages for details.

The following concepts describe an analytical system using data-center cooling
pump measurements.

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

## Profile

<p class="cv-function-subtitle">A selected grain and its available features</p>

A profile is more than data. It is an analytical specification with three parts:

- A **scope** that describes what the profile covers.
- A set of **analytical operators** that produce and transform its features.
- A **unique set of features**. Each feature belongs to exactly one profile and has exactly one producing operator.

A profile selects one resolution per dimension in its ordered `grain`. This
profile selects cooling-pump and timestamp keys for minute-by-minute observations.

`Seed` identifies the dataset initializer, which can read data or
transform another profile. It returns the complete target without a merge or
an existing target input.

Other profiles could represent:

| Profile | What one row represents | Example features |
| --- | --- | --- |
| Cooling-pump reference data | One cooling pump | Rated flow, installation date |
| Minute-level telemetry | One cooling pump at one timestamp | Differential pressure, flow |
| Daily cooling-pump summaries | One cooling pump on one day | Maximum differential pressure, average flow |
| Maintenance events | One maintenance event for a cooling pump | Event type, downtime |

Note that this is analytical representation.
Data might be stored physically in different way.

<div class="concepts-visual">
  <div class="cv-profile">
    <div class="cv-scope">
      <div><span>GRAIN</span><strong>One cooling pump at one timestamp</strong></div>
      <div><span>SCOPE / DESCRIPTIVE ONLY</span><strong>Data-center cooling pump observations</strong></div>
      <div><span>CATEGORY</span><strong>Telemetry</strong></div>
    </div>
    <div class="cv-table-scroll">
      <table class="cv-table cv-model-table">
        <thead>
          <tr class="cv-bands"><th colspan="2" class="cv-key">DIMENSIONS / observation keys</th><th colspan="2" class="cv-teal">TELEMETRY / operator A</th><th class="cv-violet">LIMITS / operator B</th><th class="cv-amber">CALCULATED</th></tr>
          <tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th><th class="cv-teal">differential pressure</th><th class="cv-teal">flow</th><th class="cv-violet">limit</th><th class="cv-amber">ratio</th></tr>
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
contract: `dataframe`, `none`, or `any` for an ignored result. Explorer derives
the labels below from dataframe counts, independently of logical features.

<div class="concepts-visual">
  <div class="cv-contracts" role="group" aria-label="Function contracts by dataframe inputs and outputs">
    <div class="cv-contract">
      <span class="cv-tag">READ 0&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">no input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Returns a dataframe without receiving a framework-bound dataframe.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">TRANSFORM 1&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Transforms a dataframe into a new dataframe or fragment.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">WRITE 1&#8594;0</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">no output</span></div></div>
      <p>Consumes a dataframe for a side effect, such as a write.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">WORKFLOW ?&#8594;?</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">unknown input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">unknown output</span></div></div>
      <p>The ignored-result contract does not describe internal dataframe use.</p>
    </div>
    <div class="cv-contract cv-contract-merge">
      <span class="cv-tag">MERGE 2&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataset</span><span class="cv-slot">fragment</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Combines the current dataset with a staged fragment.</p>
    </div>
  </div>
</div>

### Read 0→1

<p class="cv-label-line"><span class="cv-label-badge"><small>frame operation</small>read</span></p>

<p class="cv-function-subtitle">No input dataframe, brings data in from a source</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div class="cv-endpoint"><span class="cv-endpoint-icon" aria-hidden="true">&#8645;</span><strong>Telemetry source</strong><span>Database or file</span><code>cooling pump = P-01<br/>09:00 through 09:02</code></div>
      <div class="cv-arrow"><span>retrieve</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">OUTPUT / 3 observations</span><table class="cv-table"><thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">time</th><th class="cv-teal">differential pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
    </div>
  </div>
</div>

### Transform 1→1

The function receives and returns one dataframe. The examples below compare
source and target grains, not function classifications. Explorer infers
[grain relationships](../reference/python/spec-vocabulary.md#derived-grain-relationships)
from dimension resolutions, without choosing the calculation.

#### Enrich the current dataset

<p class="cv-label-line"><span class="cv-label-badge"><small>grain relationship</small>same</span></p>

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

#### Align another profile at the same grain

<p class="cv-label-line"><span class="cv-label-badge"><small>grain relationship</small>same</span></p>

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

#### Use a coarser source in a finer target

<p class="cv-label-line"><span class="cv-label-badge"><small>grain relationship</small>expand</span></p>

<p class="cv-function-subtitle">The target adds dimensions or selects finer resolutions</p>

A fragment can carry only the pump key. The merge attaches its value to
existing pump-and-time rows.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE PROFILE / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-violet">8</td></tr></tbody></table><p class="cv-detail">One value for the pump.</p></div>
      <div class="cv-arrow"><span>extend</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET FRAGMENT / pump + time</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
    </div>
  </div>
</div>

#### Summarize a finer source into a coarser target

<p class="cv-label-line"><span class="cv-label-badge"><small>grain relationship</small>collapse</span></p>

<p class="cv-function-subtitle">The target removes dimensions or selects coarser resolutions</p>

The implementation performs the aggregation. The relationship alone does not.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE / pump + time grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>aggregate</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-amber">max_pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-amber">8</td></tr></tbody></table><p class="cv-detail">One row summarizes the three moments.</p></div>
    </div>
  </div>
</div>

### Write 1→0

The function receives one dataframe and returns nothing, so it declares no
materialized features.

<p class="cv-label-line"><span class="cv-label-badge"><small>frame operation</small>write</span></p>

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

### Workflow unknown→unknown

With `returns="any"`, Explorer does not describe internal dataframe use.
An opaque workflow receives no framework-bound dataframe and may read,
calculate, and write internally. Its result is ignored.

<p class="cv-label-line"><span class="cv-label-badge"><small>frame operation</small>workflow</span></p>

<p class="cv-function-subtitle">Result is ignored, no dataframe output</p>

Logical workflow outputs establish dependencies, not dataframe columns.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-endpoint">
      <span class="cv-tag">WORKFLOW / ONE FUNCTION</span>
      <strong>External workflow</strong>
      <span>Read source <span aria-hidden="true">&rarr;</span> calculate <span aria-hidden="true">&rarr;</span> write result</span>
    </div>
  </div>
</div>

### Merge 2→1

<p class="cv-function-subtitle">Combine the current dataset with a staged fragment</p>

Merge combines the current dataset and a computed fragment, returning the
complete target. Feature consumers wait for it to succeed.

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

Every operator has one `compute` binding and optionally a `merge` binding.
Compute accepts zero or one dataframe. Its dataframe result is the complete
target without a merge, or a fragment with a merge. Foreign feature inputs
alone do not require a merge. Publish operators declare inputs and no outputs.

In this example, the operator declares its features and binds `divide` to the
current dataframe and feature identifiers.

<div class="concepts-visual">
  <div class="cv-operation cv-mapping-flow" role="group" aria-label="Input dataframe, Python operator, and output dataframe">
    <div class="cv-mapping-stage cv-mapping-inputs">
      <span class="cv-tag">INPUT DATAFRAME / declared features</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td></tr></tbody></table>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-call">
      <span class="cv-tag">OPERATOR / PRESSURE RATIO</span>
      <p>Declares pressure and limit as inputs and pressure ratio as its output.
      Binds the divide function to the dataset and feature identifiers.</p>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-outputs">
      <span class="cv-tag">OUTPUT DATAFRAME / declared feature</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th><th class="cv-amber">pressure_ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr></tbody></table>
    </div>
    <p class="cv-takeaway"><strong>Two complementary declarations.</strong> Feature inputs and outputs describe data dependencies. Compute arguments provide the dataframe and feature identifiers the function uses. An identifier argument alone does not declare an input dependency.</p>
  </div>
</div>
