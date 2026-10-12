# Infographic

The examples below use pump measurements to show how entities, datasets,
features, mappings, and functions describe an analytical system.

## Entity

<p class="cv-function-subtitle">The analytical subject</p>

<div class="concepts-visual">
  <div class="cv-entity">
    <div>
      <p>An <strong>entity</strong> is an analytical subject. Here, it is pump telemetry: measurements describing pumps over time.</p>
      <p>P-01 identifies a real pump. Pressure and flow measurements connect its physical behavior to the analytical model.</p>
    </div>
    <div class="cv-pump">
      <svg viewBox="0 0 240 200" role="img" aria-label="A pump with pressure and flow measurements">
        <circle cx="120" cy="100" r="88" fill="none" stroke="#bdccdf" stroke-dasharray="3 8"/>
        <path d="M24 105H73M164 105H218" fill="none" stroke="#6087b2" stroke-width="12"/>
        <circle cx="120" cy="105" r="45" fill="#edf2f8" stroke="#6087b2" stroke-width="3"/>
        <circle cx="120" cy="105" r="13" fill="#dff5ef" stroke="#14634f" stroke-width="3"/>
        <path d="M120 76V92M133 105H149M120 118V134M91 105H107" fill="none" stroke="#14634f" stroke-width="3" stroke-linecap="round"/>
        <path d="M86 148L78 171H162L154 148" fill="#eaf1fc" stroke="#6087b2" stroke-width="2"/>
      </svg>
      <div class="cv-sensor cv-sensor-pressure"><span>PRESSURE</span><strong>6 <small>bar</small></strong></div>
      <div class="cv-sensor cv-sensor-flow"><span>FLOW</span><strong>12 <small>L/s</small></strong></div>
      <span class="cv-pump-id">P-01 / 09:00</span>
    </div>
  </div>
</div>

## Dataset

<p class="cv-function-subtitle">The entity's observations at a defined row scope</p>

An entity can have several datasets, each describing a different row scope.
This dataset contains minute-by-minute observations of the pump entity above.

Other datasets could represent:

| Dataset | What one row represents | Example features |
| --- | --- | --- |
| Pump reference data | One pump | Rated flow, installation date |
| Minute-level telemetry | One pump at one timestamp | Pressure, flow |
| Daily pump summaries | One pump on one day | Maximum pressure, average flow |
| Maintenance events | One maintenance event for a pump | Event type, downtime |

<div class="concepts-visual">
  <div class="cv-dataset">
    <div class="cv-scope">
      <div><span>GRAIN</span><strong>One pump at one timestamp</strong></div>
      <div><span>FILTERING</span><strong>P-01, 09:00 to 09:02</strong></div>
      <div><span>COVERAGE</span><strong>Every minute in this interval</strong></div>
    </div>
    <div class="cv-table-scroll">
      <table class="cv-table cv-model-table">
        <thead>
          <tr class="cv-bands"><th colspan="2" class="cv-key">DIMENSIONS / observation keys</th><th colspan="2" class="cv-teal">TELEMETRY / mapping A</th><th class="cv-violet">LIMITS / mapping B</th><th class="cv-amber">CALCULATED</th></tr>
          <tr><th class="cv-key">pump</th><th class="cv-key">timestamp</th><th class="cv-teal">pressure</th><th class="cv-teal">flow</th><th class="cv-violet">limit</th><th class="cv-amber">ratio</th></tr>
        </thead>
        <tbody>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-teal">12</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-teal">14</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-teal">10</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr>
        </tbody>
      </table>
    </div>
    <p class="cv-legend-title">Color key for all examples</p>
    <dl class="cv-legend">
      <div><dt><span class="cv-swatch cv-key" aria-hidden="true"></span>Blue</dt><dd><strong>Dimension keys</strong><span>pump + timestamp identify an observation, not a measured value.</span></dd></div>
      <div><dt><span class="cv-swatch cv-teal" aria-hidden="true"></span>Teal</dt><dd><strong>Telemetry features</strong><span>pressure and flow are outputs of mapping A.</span></dd></div>
      <div><dt><span class="cv-swatch cv-violet" aria-hidden="true"></span>Violet</dt><dd><strong>Limit features</strong><span>limit is an output of mapping B and keeps its color when aligned or expanded.</span></dd></div>
      <div><dt><span class="cv-swatch cv-amber" aria-hidden="true"></span>Amber</dt><dd><strong>Calculated features</strong><span>ratio and max_pressure are produced by vectorize or aggregate functions.</span></dd></div>
    </dl>
    <p class="cv-detail">Colors identify column roles throughout the page, not which cells changed. Headers and labels carry the same meaning without color. Neutral cells describe arguments or operations.</p>
  </div>
</div>

The combined dataset is a conceptual view, not a requirement to store all
intermediate columns in one physical table.

## Mapping

<p class="cv-function-subtitle">A function binding associated with one or more output features</p>

A mapping connects a function binding to the feature identifiers it produces.
The two mappings below account for the teal and violet feature columns in the
dataset above. This is a logical relationship; compilation may group mappings
into physical fragments for execution.

<div class="concepts-visual">
  <div class="cv-mappings">
    <div class="cv-mapping-grid">
      <div class="cv-mini-card cv-mapping-a">
        <span class="cv-tag">MAPPING A / telemetry</span>
        <p>One function binding is associated with pressure and flow.</p>
        <table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-teal">flow</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-teal">12</td></tr></tbody></table>
      </div>
      <div class="cv-mini-card cv-mapping-b">
        <span class="cv-tag">MAPPING B / limits</span>
        <p>Another function binding is associated with the matching limit.</p>
        <table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr></tbody></table>
      </div>
    </div>
    <p class="cv-takeaway"><strong>One binding, declared outputs.</strong> Mapping A produces multiple features; mapping B produces another feature. The compiler and engine determine how these outputs are physically grouped and aligned.</p>
  </div>
</div>

## Functions

A **function template** defines reusable code and argument types.

In the compact tables, `time` abbreviates `timestamp`. Pressure and limits are
in bar; tables without a pump column still describe P-01. Column colors follow
the dataset legend above, including on both sides of each transformation.

### Read

<p class="cv-function-subtitle">Bring observations in</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div class="cv-endpoint"><span class="cv-endpoint-icon" aria-hidden="true">&#8645;</span><strong>Telemetry source</strong><span>Database or file</span><code>pump = P-01<br/>09:00 through 09:02</code></div>
      <div class="cv-arrow"><span>retrieve</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">OUTPUT / 3 observations</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
    </div>
    <p class="cv-takeaway"><strong>Boundary crossed: source to analytics.</strong> The returned dataframe contains dimension keys and declared features.</p>
  </div>
</div>

### Vectorize

<p class="cv-function-subtitle">Add a feature, keep the rows</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">BEFORE / input features</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>divide</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">AFTER / one new feature</span><table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-amber">0.50</td></tr></tbody></table></div>
    </div>
    <p class="cv-takeaway"><strong>Exactly one output feature. No new rows.</strong> Here, ratio = pressure / limit. The existing limit column is omitted from the after-view only for space.</p>
  </div>
</div>

### Conform

<p class="cv-function-subtitle">Align with the target row scope</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE / wider time selection</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr class="cv-muted-row"><td class="cv-key">P-01</td><td class="cv-key">08:59</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>align</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET / telemetry keys</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
    </div>
    <p class="cv-takeaway"><strong>The target scope is the contract.</strong> This example excludes an out-of-scope observation. The binding's implementation defines how alignment is performed.</p>
  </div>
</div>

### Expand

<p class="cv-function-subtitle">Broaden dimensional coverage</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">SOURCE DATASET / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-violet">8</td></tr></tbody></table><p class="cv-detail">One value for the pump.</p></div>
      <div class="cv-arrow"><span>extend</span><b aria-hidden="true">&#8594;</b></div>
      <div><span class="cv-tag">TARGET FRAGMENT / pump + time</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-violet">8</td></tr></tbody></table></div>
    </div>
    <p class="cv-takeaway"><strong>One observation becomes three in this example.</strong> Unlike conform's target-scope alignment, expand explicitly broadens dimensional coverage.</p>
  </div>
</div>

### Collapse and Aggregate

<p class="cv-function-subtitle">Move to a coarser grain</p>

`collapse` is the operation that groups source observations and returns a
dataset at the target grain. It uses `aggregate` analytical functions to
calculate output features within each group.

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform cv-collapse-transform">
      <div><span class="cv-tag">SOURCE / pump + time grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-teal">pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td></tr></tbody></table></div>
      <div class="cv-collapse-operation">
        <span class="cv-tag">COLLAPSE OPERATION</span>
        <p>Group by <span class="cv-key">pump</span></p>
        <div class="cv-aggregate-function">
          <strong>Aggregate function</strong>
          <code>maximum(pressure)</code>
          <p><span class="cv-teal">6, 8, 4</span> &#8594; <span class="cv-amber">8</span></p>
        </div>
        <p class="cv-detail">Return group keys and calculated features.</p>
      </div>
      <div><span class="cv-tag">TARGET / pump grain</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-amber">max_pressure</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-amber">8</td></tr></tbody></table><p class="cv-detail">One row summarizes the three moments.</p></div>
    </div>
    <p class="cv-takeaway">Each aggregate binding produces one feature per group within collapse, not a separate mapping. Multiple bindings can calculate multiple summary features.</p>
  </div>
</div>

### Write

<p class="cv-function-subtitle">Deliver or evaluate results</p>

<div class="concepts-visual">
  <div class="cv-operation">
    <div class="cv-transform">
      <div><span class="cv-tag">INPUT / selected features</span><table class="cv-table"><thead><tr><th class="cv-key">pump</th><th class="cv-key">time</th><th class="cv-amber">ratio</th></tr></thead><tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-amber">0.50</td></tr></tbody></table></div>
      <div class="cv-arrow"><span>deliver</span><b aria-hidden="true">&#8594;</b></div>
      <div class="cv-endpoint"><span class="cv-endpoint-icon" aria-hidden="true">&#8599;</span><strong>Your destination</strong><span>Persist to a database or file.<br/>Print a report.<br/>Evaluate the results.</span></div>
    </div>
    <p class="cv-takeaway"><strong>Boundary crossed: analytics to use.</strong> Keep external I/O in read and write functions, not analytical transformations.</p>
  </div>
</div>

## Specification

The specification connects the data model and its calculations in one JSON
document. Author it directly or generate it from Python or another client.

<div class="concepts-visual">
  <div class="cv-operation">
    <span class="cv-tag">ONE SPECIFICATION / STRUCTURE</span>
    <div class="cv-spec-tree">
      <div><strong>dimensions</strong><span>Shared observation keys</span><code>pump, timestamp</code></div>
      <div><strong>functions</strong><span>Reusable implementations and argument types</span><code>vectorize.divide</code></div>
      <div class="cv-spec-entity"><strong>entities</strong><span>Analytical subjects</span><div class="cv-spec-nested"><strong>pump_telemetry</strong><div class="cv-spec-nested"><strong>datasets</strong><span>Row scope, features, mappings, and writes</span><code>features / mappings / write</code></div></div></div>
    </div>
    <div class="cv-spec-example">
      <div class="cv-spec-code">
        <span class="cv-tag">EXCERPT / A DATASET'S FEATURES AND MAPPINGS</span>
        <pre><code>{
  <span class="cv-teal">"features"</span>: {
    <span class="cv-amber">"pressure_ratio"</span>: {
      "type": "float"
    }
  },
  <span class="cv-violet">"mappings"</span>: {
    "pressure_ratio": {
      "binding": {
        "function": "divide",
        "args": {
          "numerator": "$features.pressure",
          "denominator": "$features.limit"
        }
      },
      "features": ["pressure_ratio"]
    }
  }
}</code></pre>
      </div>
      <dl class="cv-spec-notes">
        <div><dt class="cv-amber">Feature registry</dt><dd>pressure_ratio is declared once as a feature with metadata.</dd></div>
        <div><dt>Function binding</dt><dd>divide selects the reusable function and binds its input references.</dd></div>
        <div><dt class="cv-violet">Mapping outputs</dt><dd>The mapping associates its function binding with pressure_ratio.</dd></div>
        <div><dt>Input references</dt><dd><span class="cv-teal">pressure</span> and <span class="cv-violet">limit</span> declare the mapping's dependencies.</dd></div>
      </dl>
    </div>
    <p class="cv-takeaway">This excerpt assumes pressure, limit, and divide are declared elsewhere in the specification. The compiler resolves the references and may group mappings into physical fragments; the engine calculates the values.</p>
  </div>
</div>

See the [Open Analytics Specification](../specification/specification.md) for
the complete document structure and reference rules, and
[Project architecture](architecture.md) for the authoring, compilation, and
execution boundaries.
