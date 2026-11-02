# Execution engine

`uptimely.engine` executes the saved plan in a validated project build bundle.
It reads runtime declarations from the bundled Spec and uses project context
to resolve function entrypoints. Backend settings and global parameters are
configured separately.

`engine.run()` executes without per-step runtime validation by default.
Use `engine.run(validate=True)` to validate input features, schema/types,
dimension-key uniqueness, row-count and key preservation, and output collisions
at every step for eager and lazy frames. Lazy value checks may repeatedly execute
upstream queries. Configuration and saved-build checks are always enabled.

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

Validation is controlled by `Engine.run(validate=True)`, not backend
configuration. The former `validate_lazy_frames` option has been removed.
Direct backend value queries execute lazy frames when needed; normal engine
execution does not call these checks unless validation is enabled.
See [runtime validation](../components/engine.md#runtime-validation) for details.

::: uptimely.engine.dataframe.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [PolarsBackend]

</div>
