# Execution engine

`uptimely.engine` executes the saved plan in a validated project build bundle.
It reads runtime contracts from plan invocations and uses project context
to resolve function entrypoints. Backend settings and global parameters are
configured separately.

`engine.run()` executes without per-step runtime validation by default.
Use `engine.run(validate=True)` to validate input features, schema/types,
dimension-key uniqueness, row-count and key preservation, and output collisions
at every step for eager and lazy frames. Lazy value checks may repeatedly execute
upstream queries. Configuration and saved-build checks are always enabled.

## Main frames and fragments

Each logical dataset has one `MainFrame`, which owns its accumulated physical
`dataframe` and explicit `id_columns`. `Fragment.stage(...)` calls an invocation
loader, checks the raw result using the run's validation policy, derives its
carried keys, and projects declared outputs. It returns a fragment ready to merge,
without requiring an already-created result dataframe. Fragments describe source
reads, foreign-dataset contributions, and same-grain calculations, retaining
their carried dimensions and producing invocation. Staging preserves lazy
execution unless enabled validation needs to inspect values.

`MainFrame(backend, id_columns, dataframe=None)` needs neither a `Dataset` nor
a Spec. The invocation executor translates dataset dimensions into physical ID
column names. Invocation-based result validation and output projection happen during
fragment staging, before assembly; `MainFrame` does not interpret invocation metadata.
Argument binding uses `invocation.argument_types`; staging and validation use
`invocation.id_columns`, `invocation.column_types`, and the invocation's function
kind. The compiler resolves these values from declarations. Runtime execution
does not receive Dataset objects or traverse the bundled Spec.

`MainFrame.merge(fragment)` accepts a prepared fragment and selects assembly by
its keys:

- Equal dimension sets: full join, retaining partial or disjoint row scopes.
- A strict subset of dimensions: left join over the existing dataset scope.
- An empty strict subset: cross join to broadcast a global value.

The first full-grain fragment initializes the main dataframe. A lower-grain
fragment requires an existing main dataframe. Successful merges update the
accumulator and return the fragment unchanged.
Validation failures leave the accumulated dataframe unchanged.

`RuntimeState.main_frames` indexes accumulators by dataset ID. Each main frame
owns its `fragments` mapping. The executor passes the producing action's mapping
ID explicitly as `merge(..., fragment_id=...)`, retaining the prepared fragment
only after a successful merge. Without an ID, a merge does not retain a reference. Fragment
lookup searches these owners and rejects names ambiguous across datasets;
dataset IDs take precedence over fragment names.
`RuntimeState.resolve_main_frame_or_fragment_dataframe(identifier)` explicitly
resolves either reference kind to its underlying dataframe.

A run selects one validation policy used by its invocation executor.
Normal execution uses no-op hooks. The executor checks inputs before calling
functions, shares its policy with fragment staging for result checks before
projection, and checks assembly contracts before joining or state updates.
Validated execution passes explicit join cardinalities to the physical merge. User functions
and `ExecutionResult.main_frames` continue to receive
ordinary Polars dataframes or lazy frames, not these internal runtime wrappers.

`MainFrame` and `Fragment` are available from `uptimely.engine`. They replace
the internal `DataFrameExecution` assembly helper.

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

`ExecutionResult.main_frames` maps each project-wide unique dataset ID to its final
dataframe, for example `result.main_frames["telemetry"]`.
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

## runtime frames

::: uptimely.engine.dataframe.main_frame
    options:
      heading_level: 3
      show_root_heading: false
      members: [MainFrame]

::: uptimely.engine.dataframe.fragment
    options:
      heading_level: 3
      show_root_heading: false
      members: [Fragment]

## backend

`uptimely.engine.dataframe.backend` defines adapter protocols and their built-in
implementations.

Backend methods operate only on dataframe values, column names, keys, and join
cardinalities. Full, left, and cross joins are reusable operations. Backends do
not know about logical datasets, main frames, fragments, or invocation contracts;
dimension-aware assembly belongs to `MainFrame`.

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
