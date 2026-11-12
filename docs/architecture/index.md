# Architecture

Uptimely has five core components: Project, Spec, Compiler, Engine, and
Explorer.

Spec is the definition for analytical system. Project builds a portable bundle containing spec, and resolved execution plan by the Compiler. Engine executes that plan, and the Explorer presents build and run
information for inspection.

## From definition to results

<p class="cv-function-subtitle">Define the Spec, build a bundle, run it, then inspect the workflow and results.</p>

<div class="concepts-visual architecture-visual">
  <div class="av-journey">
    <section class="av-phase" aria-labelledby="av-define">
      <span class="cv-tag">01 / DEFINE</span>
      <h3 id="av-define">Describe the analytics</h3>
      <div class="av-flow">
        <div class="av-node av-authoring">
          <span class="av-node-label">OPTIONAL</span>
          <strong>Python authoring</strong>
          <span>Use imports, helpers, and editor assistance</span>
        </div>
        <div class="av-connector"><span>exports to</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-definition">
          <span class="av-node-label">SPEC</span>
          <strong>Spec JSON</strong>
          <span>Portable analytics definition, also authored directly as JSON</span>
        </div>
      </div>
    </section>
    <div class="av-bridge" aria-hidden="true">&#8594;</div>
    <section class="av-phase" aria-labelledby="av-build">
      <span class="cv-tag">02 / BUILD</span>
      <h3 id="av-build">Prepare a build bundle</h3>
      <div class="av-flow">
        <div class="av-node av-project av-operator">
          <span class="av-node-label">PROJECT</span>
          <strong>Builder</strong>
          <span>Loads the Spec and orchestrates the build</span>
        </div>
        <div class="av-connector"><span>compiles with</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-operator">
          <span class="av-node-label">COMPILER</span>
          <strong>Validate and plan</strong>
          <span>Resolves dependencies, binds arguments, and orders function invocations</span>
        </div>
        <div class="av-connector"><span>produces</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-definition">
          <span class="av-node-label">BUNDLE</span>
          <strong>Build bundle</strong>
          <span>Contains the Spec and portable execution plan</span>
        </div>
      </div>
    </section>
    <div class="av-bridge" aria-hidden="true">&#8594;</div>
    <section class="av-phase" aria-labelledby="av-run">
      <span class="cv-tag">03 / EXECUTE</span>
      <h3 id="av-run">Run the analytics</h3>
      <div class="av-flow">
        <div class="av-node av-operator">
          <span class="av-node-label">ENGINE</span>
          <strong>Execute the resolved plan</strong>
          <span>Runs Python functions according to the plan</span>
        </div>
        <div class="av-connector"><span>returns</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-result">
          <span class="av-node-label">RUN OUTPUT</span>
          <strong>Results and run details</strong>
          <span>Calculated outputs, statuses, and diagnostics</span>
        </div>
      </div>
    </section>
    <div class="av-bridge" aria-hidden="true">&#8594;</div>
    <section class="av-phase" aria-labelledby="av-inspect">
      <span class="cv-tag">04 / INSPECT</span>
      <h3 id="av-inspect">Explore the workflow</h3>
      <div class="av-flow">
        <div class="av-node av-result">
          <span class="av-node-label">EXPLORER</span>
          <strong>Inspect the project</strong>
          <span>Present the Spec as a browsable catalog, visualize dependency lineage, draw the execution plan, and inspect run results.</span>
        </div>
      </div>
    </section>
  </div>
  <dl class="cv-legend av-legend" aria-label="Architecture diagram color key">
    <div><dt aria-label="Optional authoring"><span class="cv-swatch av-swatch-authoring" aria-hidden="true"></span></dt><dd><strong>Optional authoring</strong><span>Python can export a Spec, or write JSON directly.</span></dd></div>
    <div><dt aria-label="Portable artifacts"><span class="cv-swatch cv-key" aria-hidden="true"></span></dt><dd><strong>Portable artifacts</strong><span>Spec JSON and the build bundle.</span></dd></div>
    <div><dt aria-label="Build and execution"><span class="cv-swatch cv-teal" aria-hidden="true"></span></dt><dd><strong>Build and execution</strong><span>Project/Builder orchestrates compilation; the Compiler plans and the Engine runs.</span></dd></div>
    <div><dt aria-label="Inspection and results"><span class="cv-swatch cv-amber" aria-hidden="true"></span></dt><dd><strong>Inspection and results</strong><span>The Explorer presents generated project and run information.</span></dd></div>
  </dl>
</div>

Python authoring is optional: it supports imports, helpers, reuse, and editor
assistance, then exports to Spec JSON. Spec JSON can also be authored
directly.
