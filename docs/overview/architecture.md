# Project architecture

Uptimely separates spec definition, planning, and execution. The same
declarative definition can be compiled into a portable plan and run by an
engine.

## From definition to results

<p class="cv-function-subtitle">Define the spec, prepare a plan, then execute it.</p>

<div class="concepts-visual architecture-visual">
  <div class="av-journey">
    <section class="av-phase" aria-labelledby="av-define">
      <span class="cv-tag">01 / DEFINE</span>
      <h3 id="av-define">Describe the spec</h3>
      <div class="av-flow">
        <div class="av-node av-authoring">
          <span class="av-node-label">OPTIONAL</span>
          <strong>Python authoring</strong>
          <span>A developer-friendly way to write definitions</span>
        </div>
        <div class="av-connector"><span>export</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-definition">
          <span class="av-node-label">SOURCE OF TRUTH</span>
          <strong>Spec JSON</strong>
          <span>Or write this document directly</span>
        </div>
      </div>
    </section>
    <div class="av-bridge" aria-hidden="true">&#8594;</div>
    <section class="av-phase" aria-labelledby="av-prepare">
      <span class="cv-tag">02 / PREPARE</span>
      <h3 id="av-prepare">Make a run plan</h3>
      <div class="av-flow">
        <div class="av-node av-action">
          <span class="av-node-label">COMPILER</span>
          <strong>Optimize the plan</strong>
          <span>Resolves dependencies and execution order</span>
        </div>
        <div class="av-connector"><span>produces</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-definition">
          <span class="av-node-label">PORTABLE PLAN</span>
          <strong>Execution plan</strong>
          <span>What runs, and in what order</span>
        </div>
      </div>
    </section>
    <div class="av-bridge" aria-hidden="true">&#8594;</div>
    <section class="av-phase" aria-labelledby="av-run">
      <span class="cv-tag">03 / RUN</span>
      <h3 id="av-run">Get the results</h3>
      <div class="av-flow">
        <div class="av-node av-action">
          <span class="av-node-label">ENGINE</span>
          <strong>Execute the plan</strong>
          <span>Connects the plan to live data and functions</span>
        </div>
        <div class="av-connector"><span>returns</span><b aria-hidden="true">&#8595;</b></div>
        <div class="av-node av-result">
          <span class="av-node-label">OUTPUT</span>
          <strong>Analytical results</strong>
          <span>Calculated outputs and run details</span>
        </div>
      </div>
    </section>
  </div>
  <dl class="cv-legend av-legend" aria-label="Architecture diagram color key">
    <div><dt><span class="cv-swatch av-swatch-authoring" aria-hidden="true"></span>Gray</dt><dd><strong>Optional authoring</strong><span>Python source for writing spec definitions.</span></dd></div>
    <div><dt><span class="cv-swatch cv-key" aria-hidden="true"></span>Blue</dt><dd><strong>Definitions</strong><span>Spec JSON and the portable execution plan.</span></dd></div>
    <div><dt><span class="cv-swatch cv-teal" aria-hidden="true"></span>Teal</dt><dd><strong>Actions</strong><span>The compiler prepares the plan; the engine executes it.</span></dd></div>
    <div><dt><span class="cv-swatch cv-amber" aria-hidden="true"></span>Amber</dt><dd><strong>Results</strong><span>Calculated outputs and details from a run.</span></dd></div>
  </dl>
</div>

Python authoring is optional: it supports imports, helpers, reuse, and editor
assistance, then exports to Spec JSON. Spec JSON can also be authored
directly.

## Spec

Spec JSON is the portable, authoritative definition of the spec. It
describes subjects, datasets, features, functions, and actions without
depending on a particular authoring language. The other tools consume this
shared contract.

The Spec declares functions and actions. An action says what data a function
reads and writes. The compiler records each action as a planned step; the
engine runs those steps using the Python functions. Building a plan does not
run the analytics.

## Compiler

The compiler checks the Spec and creates an execution plan that lists the work
and its order. The engine supplies runtime values and runs the plan.

## Engine

The engine runs the plan saved in the build bundle, using the bundled Spec and
the runtime configuration. It returns calculated outputs and details about
the run, including successes and failures.

Separating definition, planning, and execution keeps spec portable while
allowing plans to run in different environments.
