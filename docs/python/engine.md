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
`EngineValidator` checks plan/backend compatibility during engine construction,
independently of the run's `validate` flag.

## Main frames and fragments

Each profile has one `MainFrame`, which owns its accumulated physical
`dataframe` and explicit `id_columns`. `Fragment.stage(...)` calls a compute
invocation's loader, checks the raw result with `FragmentValidator` when
`validate=True`, derives its carried keys, and projects declared outputs. The
executor retains that fragment by compute invocation ID without changing the
profile's accumulated dataframe.

The separately scheduled merge invocation resolves its pending fragment and
current target, then calls the merge function declared by the Spec. The default
merge function uses `merge_by_grain`; a custom merge replaces it and is never
silently retried with the default. A merge function returns the complete new
target dataframe. The executor checks its structure and declared columns, then
publishes it by assignment; it does not merge the returned frame a second time.
The fragment is retained on the `MainFrame` by operator ID only after successful
publication, reusing the staged object rather than copying the dataframe.
Staging and merging preserve lazy execution unless enabled validation needs to
inspect values.

`MainFrame(backend, id_columns, dataframe=None)` needs neither a profile declaration nor
a Spec. The invocation executor translates profile grain keys into physical ID
column names. Invocation-based result validation and output projection happen during
fragment staging, before assembly; `MainFrame` does not interpret invocation metadata.
Argument binding uses `invocation.argument_types`; staging and validation use
`invocation.id_columns`, `invocation.column_types`, and the invocation's function
kind. The compiler resolves these values from declarations. Runtime execution
does not receive profile objects or traverse the bundled Spec.

`MainFrame.merge(fragment)` remains the direct physical assembly helper and
selects assembly by its keys:

- Equal dimension sets: full join, retaining partial or disjoint key coverage.
- A strict subset of dimensions: left join over the existing profile frame.
- An empty strict subset: cross join to broadcast a global value.

The first full-grain fragment initializes the main dataframe. A lower-grain
fragment requires an existing main dataframe. Successful calls update the accumulator and return the fragment unchanged.
Validation failures leave the accumulated dataframe unchanged.

`RuntimeState.main_frames` indexes accumulators by profile ID. Each main frame owns its `fragments` mapping. Fragment lookup searches these
owners and rejects names ambiguous across profiles; profile IDs take precedence
over fragment names.
`RuntimeState.resolve_main_frame_or_fragment_dataframe(identifier)` explicitly
resolves either reference kind to its underlying dataframe. Pending fragments
are keyed by compute invocation ID and become operator-name references only
after their merge succeeds.

A run passes its `validate` flag to the invocation executor and fragment staging.
When enabled, the executor calls `InvocationValidator` before invoking
operators, staging calls `FragmentValidator` before projection, and merge
checks declared types and key uniqueness before publishing. Regardless of the
flag, merge output must be a dataframe with required dimensions and the
complete expected target schema; overlapping feature columns are rejected.
Publishing is transactional with respect to the executor's assignment: a failed
merge leaves the previously published main frame unchanged. It cannot undo
mutation performed by an arbitrary user function, so merge functions must not
mutate their target input. User functions and `ExecutionResult.main_frames`
continue to receive ordinary Polars dataframes or lazy frames, not these
internal runtime wrappers.

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

`ExecutionResult.main_frames` maps each project-wide unique profile ID to its final
dataframe, for example `result.main_frames["telemetry"]`.
`ExecutionResult.calculated_outputs` maps `(profile_id, feature_id)` pairs to
dimension-keyed output dataframes, for example
`result.calculated_outputs["telemetry", "doubled"]`. Profile metadata is available
in the bundled Spec and plan invocations.
`result.invocation_statuses` reports whether each planned step succeeded,
failed, or was skipped. `result.durations` and `result.failures` give the
duration and any error for each step.

Every `Engine.run()` overwrites the latest snapshot under `_generated/run/`.
`engine.run(preview_rows=10)` changes the default five-row sample size.
Previews collect bounded lazy queries after execution while returned main
frames remain lazy. `result.duration_seconds` excludes preview collection and
publication. `result.preview_frames` contains the already-collected samples;
`result.preview_failures` reports unavailable samples separately from invocation
failures.

The snapshot contains `run.json`, structured `log.jsonl`, and one
`preview/<profile>.json` per available profile. It is not a full output store
and retains no history. Persistence errors propagate rather than returning an
apparently successful result without saved artifacts.

::: uptimely.engine.runtime.result
    options:
      heading_level: 3
      show_root_heading: false
      members: [ExecutionResult]

## Saved runs

Use the shared `RunStore` reader without importing project functions or running
analytics:

```python
import pathlib
from uptimely import run

store = run.RunStore(pathlib.Path("examples/pump_analytics"))
manifest = store.read_manifest()
sample = store.read_preview("pump_profile", run_id=manifest.run_id)
events = store.read_logs(run_id=manifest.run_id, offset=0, limit=100)
```

An optional `run_id` is a consistency token, not a history selector. If another
execution replaces the snapshot, readers raise `RunChangedError`; reload the
manifest before retrying. Run storage does not use locks. Concurrent runs and
reads during publication are not coordinated; callers should read after a run
finishes. Staging keeps the previous run available during execution and preview
collection, but the directory may be briefly unavailable during replacement.

Preview JSON contains ordered `columns` with physical dtype strings and
positional `rows`, a `head` sampling label, requested row limit, status, and
optional error. Empty frames retain their column schema. Dates and times use
ISO strings, decimals use strings, durations use Python timedelta strings, and
binary values use base64. Integers outside JavaScript's safe integer range are
strings. Non-finite floats use `"NaN"`, `"Infinity"`, or `"-Infinity"`; lists and
structs are encoded recursively. Unsupported values produce an explicit failed
preview, not silently altered data.

::: uptimely.run.store
    options:
      heading_level: 3
      show_root_heading: false
      members: [RunStore, RunChangedError, RunNotFoundError]

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
not know about profiles, main frames, fragments, or invocation contracts;
dimension-aware assembly is handled by the stateless Polars merge library.
`MainFrame` delegates assembly to that library and owns accumulator state.

### Merge functions

`uptimely.library.merge.polars.merge_by_grain(target, fragment, target_keys,
fragment_keys=None)` assembles a fragment using its carried keys. When
`fragment_keys` is omitted, the function infers carried target keys from the
fragment schema at runtime. Equal key sets use a full join, a strict subset
uses a left join, and an empty strict subset uses a cross join. With no target,
only a fragment at the complete target grain can initialize the result. The
function supports eager and lazy Polars dataframes.

::: uptimely.library.merge.polars
    options:
      heading_level: 4
      show_root_heading: false
      members: [merge_by_grain]

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
