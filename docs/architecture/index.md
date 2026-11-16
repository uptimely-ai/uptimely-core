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
See the [Compiler](compiler.md), [Execution plan](../reference/formats/execution-plan.md),
[Engine](engine.md), and [Explorer](explorer.md) pages for details.

The following concepts describe an analytical system using data-center cooling
pump measurements.
