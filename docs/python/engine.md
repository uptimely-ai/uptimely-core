# Execution engine

`uptimely.engine` executes the saved plan in a validated project build bundle.
It reads runtime declarations from the bundled Spec and uses project context
to resolve function entrypoints. Backend settings and global parameters are
configured separately.

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
      members: [EngineConfig, EngineBackendConfig, ParameterConfig]

## result

`uptimely.engine.runtime.result` describes execution outputs.

`ExecutionResult.datasets` maps each project-wide unique dataset ID to its final
dataframe, for example `result.datasets["telemetry"]`.
`ExecutionResult.calculated_outputs` maps `(dataset_id, feature_id)` pairs to
dimension-keyed output dataframes, for example
`result.calculated_outputs["telemetry", "doubled"]`. Entity IDs are not part of
either key; entity metadata is available in the bundled Spec and plan invocations.
`result.invocation_statuses` reports whether each planned step succeeded,
failed, or was skipped. `result.durations` and `result.failures` give the
duration and any error for each step.

::: uptimely.engine.runtime.result
    options:
      heading_level: 3
      show_root_heading: false
      members: [ExecutionResult]

## backend

`uptimely.engine.dataframe.backend` defines adapter protocols and their built-in
implementations.

### Adapter protocols

Implement this interface to customize dataframe operations.

::: uptimely.engine.dataframe.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [DataFrameBackend]

### Built-in adapters

The engine selects the dataframe backend using the configured `dataframe`
string. The built-in backend is Polars; runtime resources come from the bundled
Spec and function entrypoints come from the plan.

`PolarsBackend(validate_lazy_frames=False)` disables implicit execution for
data-dependent lazy-frame validation. The engine exposes the same option as
`EngineBackendConfig(validate_lazy_frames=False)`. Schema checks and deferred
Polars join validation remain enabled; explicit `collect()` calls are allowed.
See [runtime validation](../components/engine.md#runtime-validation) for the
checks skipped in this mode and its limitations.

::: uptimely.engine.dataframe.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [PolarsBackend]

</div>
