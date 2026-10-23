# Execution engine

`uptimely.engine` executes the saved plan in a validated project build bundle.
The bundle supplies plan resources and project context for resolving callable
entrypoints. Runtime configuration and environment-specific bindings are
supplied separately.

<div class="api-reference" markdown="1">

## engine

`uptimely.engine.engine` provides the execution entry point.

::: uptimely.engine.engine
    options:
      heading_level: 3
      show_root_heading: false
      members: [Engine]

## config

`uptimely.engine.config` defines runtime settings.

::: uptimely.engine.config
    options:
      heading_level: 3
      show_root_heading: false
      members: [EngineConfig, EngineBackendConfig]

## result

`uptimely.engine.result` describes execution outputs.

`ExecutionResult.datasets` maps each project-wide unique dataset ID to its final
dataframe, for example `result.datasets["telemetry"]`.
`ExecutionResult.calculated_outputs` maps `(dataset_id, feature_id)` pairs to
dimension-keyed output dataframes, for example
`result.calculated_outputs["telemetry", "doubled"]`. Entity IDs are not part of
either key; entity metadata remains available in the saved plan resources and
callables.

::: uptimely.engine.result
    options:
      heading_level: 3
      show_root_heading: false
      members: [ExecutionResult]

## backend

`uptimely.engine.backend` defines adapter protocols and their built-in
implementations.

### Adapter protocols

Implement this interface to customize dataframe operations.

::: uptimely.engine.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [DataFrameBackend]

### Built-in adapters

The engine selects the dataframe backend using the configured `dataframe`
string. The built-in backend is Polars; resources and callable entrypoints come
from the build bundle.

::: uptimely.engine.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [PolarsBackend]

</div>
