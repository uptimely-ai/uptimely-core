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
The engine checks plan/backend compatibility during construction,
independently of the run's `validate` flag.
Runtime validation checks the declared contracts for actual values, not the
business correctness of an analytical result. Keep ordinary pytest assertions
for expected values; isolate external reads, writes, and other side effects
with safe fixtures or mocks.

## Materialized datasets and fragments

The spec's `Profile` describes the analytical model. The engine's `Dataset` is
only the accumulated physical dataframe materialized for that profile; it is not
a spec declaration. Each runtime Dataset owns its `dataframe`, `identifiers`,
and `relations`; `keys` combines identifiers and relations.
`Fragment.stage(...)` calls a compute invocation's loader, asks the Fragment to
check the raw result, derives its identifiers and relations, and projects declared outputs.
Required structure and declared-output checks always run; content, uniqueness,
and type checks run when `validate=True`. The executor retains that fragment by
compute invocation ID without changing the profile's accumulated dataframe.

The separately scheduled merge invocation resolves its pending fragment and
current dataset, then calls the merge function declared by the Spec. The default
merge function uses `merge_by_grain`; a custom merge replaces it and is never
silently retried with the default. A merge function returns the complete new
dataset dataframe. The runtime `Merge` checks its structure and declared columns, then the executor
publishes it by assignment; it does not merge the returned frame a second time.
The fragment is retained on the `Dataset` by operator ID only after successful
publication, reusing the staged object rather than copying the dataframe.
Staging and merging preserve lazy execution unless enabled validation needs to
inspect values.

`Dataset(backend, identifiers, dataframe=None, relations=())` needs neither a profile declaration
nor a Spec. The invocation executor translates profile grain members into physical ID
column names. Ownership is split explicitly:

- `Fragment` stages and validates compute results, carrying `identifiers` for
  row identity and `relations` for links to other grains. Its `keys` combines
  both for merging. Merge code does not inspect its invocation.
- `Merge(dataset, fragment)` checks collisions, executes the configured assembly,
  and validates its complete result without changing dataset state.
- `Dataset` owns the accumulated frame, retained fragments, and grain/type checks.

The invocation executor checks
vectorized results against invocation-specific contracts before publication.
These operations use `invocation.target_identifiers`,
`invocation.fragment_keys`, `invocation.column_types`, and the
invocation's derived operator policy where needed. The compiler resolves these values from
declarations. Runtime execution does not receive profile objects or traverse the
bundled Spec.

An expansion can return a source-resolution feature and its identifiers without
performing its own join. Parent-resolution IDs are dimension identifiers, not
analytical features. Declare these related-profile resolutions in `relations`.
The compiler includes the selected identifiers and explicitly declared relation
columns in `fragment_keys`. Staging retains
these columns when they occur in the data,
without requiring feature declarations or interface outputs. Other undeclared
columns are discarded. Their types are validated when runtime validation is enabled.

The merge uses the resolution identifiers present in the fragment. They must
already be available on the target; no reader or identifier-producer dependencies
are inferred. A missing target identifier fails the merge rather than falling
back to a cross join. Full-grain fragments merge by the declared grain and
coalesce shared relations. Lower-resolution fragments left-join by their
carried identifiers without changing the target grain. The current portable
plan requires this metadata; older plan versions are rejected and must be
rebuilt from the source Spec. Rebuild after changing these declarations.

`Dataset.merge(fragment)` delegates to `Merge` for automatic assembly and publishes
only after checks succeed. `Merge.execute(load)` accepts a configured merge
callable; without one, it uses the shared key-based merge function:

- Equal dimension sets: full join, retaining partial or disjoint key coverage.
- A strict subset of dimensions: left join over the existing profile frame.
- An empty strict subset: cross join to broadcast a global value.

The first full-grain fragment initializes the accumulated dataframe. A
lower-grain fragment requires an existing Dataset. Successful calls update the
accumulator and return the fragment unchanged.
Validation failures leave the accumulated dataframe unchanged.

`RuntimeState.datasets` maps profile IDs to materialized Datasets. Each
Dataset owns its `fragments` mapping. Fragment lookup searches these datasets and
rejects names ambiguous across profiles; profile IDs take precedence
over fragment names.
`RuntimeState.resolve_dataset_or_fragment_dataframe(identifier)` explicitly
resolves either reference kind to its underlying dataframe. Pending fragments
are keyed by compute invocation ID and become operator-name references only
after their merge succeeds.

A run passes its `validate` flag to the invocation executor and fragment staging.
When enabled, the invocation executor checks input requirements before invoking
operators, `Fragment` checks optional content contracts before projection, and
`Merge` validates its result against the dataset's grain and types before publishing. Regardless of the
flag, merge output must be a dataframe with required dimensions and the complete
expected target schema; overlapping feature columns are rejected.
Publishing is transactional with respect to the executor's assignment: a failed
merge leaves the previously published Dataset unchanged. It cannot undo
mutation performed by an arbitrary user function, so merge functions must not
mutate their dataset input. User functions and `ExecutionResult.datasets`
continue to receive ordinary Polars dataframes or lazy frames, not these
internal runtime wrappers.

`Dataset`, `Fragment`, and `Merge` are available from `uptimely.engine`. They replace
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

`ExecutionResult.datasets` maps each project-wide unique profile ID to its final
dataframe, for example `result.datasets["telemetry"]`.
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

::: uptimely.engine.dataframe.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [Dataset]

::: uptimely.engine.dataframe.fragment
    options:
      heading_level: 3
      show_root_heading: false
      members: [Fragment]

::: uptimely.engine.dataframe.merge
    options:
      heading_level: 3
      show_root_heading: false
      members: [Merge]

## backend

`uptimely.engine.dataframe.backend` defines adapter protocols and their built-in
implementations.

Backend methods operate only on dataframe values, column names, keys, and join
cardinalities. Full, left, and cross joins are reusable operations. Backends do
not know about profiles, materialized Datasets, fragments, or invocation contracts;
dimension-aware assembly is handled by the stateless Polars merge library.
`Merge` delegates automatic assembly to that library; `Dataset` owns accumulator state.

### Merge functions

`uptimely.library.merge.polars.merge_by_grain(dataset, fragment, dataset_identifiers,
fragment_keys=None)` assembles a fragment using its carried keys. When
`fragment_keys` is omitted, the function infers carried dataset keys from the
fragment schema at runtime. Equal key sets use a full join, a strict subset
uses a left join, and an empty strict subset uses a cross join. With no dataset,
only a fragment at the complete dataset grain can initialize the result. The
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
Direct backend value queries execute lazy frames when needed. Expensive content
checks run only when validation is enabled; basic fragment and vectorize
structure checks still run during normal execution.
See [runtime validation](../architecture/engine.md#runtime-validation) for details.

::: uptimely.engine.dataframe.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [PolarsBackend]

</div>
