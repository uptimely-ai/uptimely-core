# Application {#app}

The application layer is the configured entry point for using Uptimely. It loads
configuration, composes the build and execution components, and coordinates a
requested operation for one project.

Commands such as `uptimely build` and `uptimely run` use this layer to apply
configuration and invoke the lower-level components. Project structure and
path conventions belong to the [project layer](project.md).

## Config

The main application configuration is stored in `uptimely.toml`.

The main settings can be overriden by custom config files. Typical setup is to have `development`, `qa` and `production` configs separately. But configs can also override settings for focused debugging.

Finally, some settings can be overriden by cli arguments or python class attributes.

Read details and example from guides section.

## Workflow

Application is responsible to prepare the state for build and engine.

Configuration makes application aware of where to read the requires resources and where write the results.

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
          <strong>Build bundle</strong>
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
  </div>
</div>
