# Functions and contracts

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
[grain relationships](grain-relationships.md#derived-grain-relationships)
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
