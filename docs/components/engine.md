# Execution engine

The built-in engine runs the portable plan in a validated build bundle. Each
invocation supplies its function entrypoint and runtime contract; the engine
calls the Python implementation and publishes results according to the plan.
Runtime configuration is supplied separately.

## Engine settings

Engine settings are supplied to `Engine`, not stored in the Spec
document. The engine implementation decides which configuration values
to use.

Construct an engine with the validated build bundle and runtime configuration.
The project configuration is stored in `config/config.json`; programmatic users
can pass a `Config` instance or provide parameter values directly.

The engine uses the configured `dataframe` string to select a dataframe
backend. The built-in Python engine currently supports `polars`.
Data-producing functions must return a Polars `DataFrame` or `LazyFrame`;
other dataframe representations and custom adapters are not supported.
`evaluation` and `batch_size` are reserved settings: they are
accepted and stored, but do not change evaluation strategy, data access, or
persistence. Do not rely on them to enable lazy execution, batching, or
persistence.

The `engine` section of `config/config.json` contains backend settings:

JSON key | Type | Purpose
--- | --- | ---
`backend` | object | Backend options validated by `EngineBackendConfig`.
`backend.type` | string | Engine type, such as `docker` or `python_venv`.
`backend.definition` | string or `null` | Folder containing configuration files for the engine.
`backend.dataframe` | string | Dataframe backend. The built-in engine currently supports `polars`.
`backend.evaluation` | string | Reserved. Values such as `eager`, `lazy`, and `persist` are stored but have no effect on execution.
`backend.batch_size` | integer, `"*"`, or `null` | Reserved. Validates positive integers, `"*"`, or `null`, but does not change how many records are read at a time.

A compiled plan records its backend
claim as `required_backend`; the built-in engine rejects values other than
`polars`. Orchestration is a deployment concern and is not represented in the
Spec document.

## Executing a build bundle

The engine accepts a validated build bundle and executes its compiled portable
plan. It reads ID columns, column types, argument types, and function kinds from
plan invocations, not from Spec models, and uses the project
root to resolve function entrypoints. A plan can be compiled for selected
output features; the compiler includes their prerequisite calculations and
dependencies, so the engine needs no special subset logic. An exported plan is
executed as part of its build bundle, without recompilation.

Execution returns profile frames, calculated outputs, per-invocation statuses and
durations, failures, and the plan version. A failed invocation is reported in
the result, and execution stops; invocations that did not run are marked skipped.

Each execution also replaces the latest diagnostic snapshot in
`_generated/run/`: metadata, JSONL logs, and bounded profile previews.
Previews collect lazy queries after execution without changing the returned
lazy frames. Preview failures are separate from invocation failures.
See [latest-run artifacts](../cli/engine.md#latest-run-artifacts) for the stored
data and [saved-run readers](../python/engine.md#saved-runs) for programmatic access.

### Row-context metadata

Operations can carry `row_context` requirements independently of their primitive
arguments. The batch engine does not pass this metadata to functions or use it
to sort, retain rows, or delay output. Future stateful implementations can inspect
the declarations, but must distinguish unknown context from explicit zero
context and account for grouping performed by functions and dependency chains.
See the [row context contract](spec.md#row-context).

## Configuration and runtime parameters

Keep framework configuration separate from profile data and analytical
inputs. Use it for values that adapt how a workflow runs in this framework, so
the same build can run in different environments without changing its
analytics. Examples include selecting read and write locations and
environment-specific storage or catalog names. Framework-owned settings can
also have defaults, such as the engine's default lazy-frame validation policy.
Other useful controls include backend, validation, materialization, execution
scope, and resource limits when supported by the engine.

Do not put records, feature values, or business thresholds in framework
configuration. Keep observations in profile dataframes and analytical inputs as declared feature
inputs in the Spec. Engine options belong in the `engine` configuration or
dedicated CLI options. The `params` map does not set engine options directly;
it supplies scalar values to function bindings. Use it for framework controls
such as a path or source identifier when a read or write function needs that
value, not for profile or analytical values.

Compute arguments may contain `$params.<name>` references. Each reference
resolves to one required scalar value from the flat `params` map in
`config/config.json`; missing entries fail explicitly. References work recursively inside argument
dictionaries and lists and do not create feature dependencies.

```json
{
  "engine": {"backend": {}},
  "params": {
    "telemetry_source": "data/telemetry.parquet",
    "output_path": "data/results.parquet"
  }
}
```

In Python authoring, `up.ref.params("telemetry_source")` and
`up.ref.params("output_path")` create references to the same map. Parameter
values support JSON strings, finite numbers, booleans, and null; arrays and
objects are rejected. These references are required bindings, not a defaulting
mechanism: a missing value fails the invocation. Defaults are appropriate for
framework-owned optional settings only when that setting defines a default;
they do not make a missing `$params` reference optional.

`config/config.json` keeps backend settings under `engine` and the flat
runtime control parameter map under `params`. Programmatic users can construct
`Config(engine=EngineConfig(...), params=Params(...))` or pass the flat map as
`parameters` to `Engine`.

## Fragments

A fragment is a subset of a profile's columns, keyed by the selected grain.
It contains those grain-key columns and the feature columns declared as
outputs by one data-producing operator. The compute invocation stages this
fragment without changing the accumulated profile frame. A separately
scheduled merge invocation calls its configured function to publish a complete
updated profile frame.

Data-producing compute invocations are declared under `read`, `conform`,
`expand`, and `collapse`. Each produces a fragment for the profile that
declares it.
`conform`, `expand`, and `collapse` take exactly one foreign/source dataframe
through a `$profiles.<id>.dataframe` binding reference. The engine does not
pass the accumulated target frame to these functions; each function transforms
its foreign input into a fragment for the target profile. `read` takes no
dataframe argument. Vectorize operations consume features from their own
profile. The engine never joins another profile implicitly.

| Type | Meaning |
| --- | --- |
| `read` | Reads data from an external source and returns it as a fragment. |
| `collapse` | Groups input data, usually at a coarser grain, and returns a fragment. |
| `expand` | Uses another profile to produce a fragment with expanded dimensional coverage. |
| `conform` | Reconciles data from a same-grain foreign profile to the target grain. |

`conform` requires source and target profiles to declare the same grain.
`collapse` requires a strictly coarser target grain; `expand` requires a
strictly finer target grain. Parent links between resolutions describe valid
coarsening and refinement. Each dimensional operator explicitly supplies its
target grain keys as matching keys, for example with
`ref.profile().grain.ids`. A dimension reference used for grouping or
ordering does not implicitly select a join key. Combining sources requires an
explicit dimensional operation; same-profile fragment assembly is
not a cross-profile reconciliation. Functions are responsible for grouping,
matching, output names, and constructing literal values.

The compiled plan groups independent invocations into stages. The built-in engine
processes stages and invocations sequentially. Profile `order` metadata does not
sort data or guarantee physical row order; order-sensitive functions must
explicitly declare and implement their ordering inputs.

## Fragment merging and row coverage

The runtime represents each profile with a physical `MainFrame` holding
its accumulated dataframe and ID column names, without profile declaration or
Spec dependencies. `Fragment.stage()` loads a compute invocation's result,
optionally validates it against the invocation's compiled contract, and
projects its declared outputs. The fragment is held pending by compute
invocation ID until the corresponding merge invocation executes.

The merge invocation receives the current target dataframe (or `None` when
initializing) and the staged fragment, calls its declared function, validates
the complete returned target schema, then publishes by assignment. The default
merge function delegates key-based assembly to the stateless
`uptimely.library.merge.polars.merge_by_grain`; custom merge functions replace
that behavior and are not retried with the default. The executor does not merge
the returned dataframe a second time. After successful publication, it retains
the staged fragment on the `MainFrame` under the operator ID without copying
the dataframe. Merge functions must not mutate their target input because
arbitrary function-side mutations cannot be rolled back.

The default `merge_by_grain` function combines full-grain fragments by the
profile's complete grain keys, never by row position. It uses a full join,
coalesces key columns, and treats null keys as equal. With validation enabled,
it requires a one-to-one key relationship. Keys present on only one side are
retained, with nulls for the other fragment's absent values. This supports
partial and disjoint coverage; equal row counts or identical key sets are not
required.

For a lower-grain `expand` fragment, the default merge function left-joins onto
the existing accumulated profile frame by the carried keys with a many-to-one
relationship, transferring each source observation to matching target
observations. A fragment with no dimension keys can hold at most one row and
is broadcast to all observations; it therefore requires an existing target
frame. These behaviors belong to the default merge function; a custom merge
function defines its own assembly behavior.

Feature columns may not overlap existing target columns. The default join is
permissive about coverage: it does not prove that fragments satisfy the
profile's declared grain. Profile `scope` is descriptive metadata only and has
no bearing on merging.
Fragments for one profile should represent the same intended observations.
Include a key with an explicit null feature value when an observation belongs
to the profile but its value is missing; use separate profiles for genuinely
different grains. A `conform` operation is responsible for reconciling its
source to the target profile's required rows before returning a fragment.

## Runtime validation

Per-step runtime validation is opt-in. Use `uptimely run --validate` (also
available as `uptimely engine run --validate`) or `Engine.run(validate=True)`
to check declared feature inputs and returned dataframe contracts at each step.
The same checks apply to eager and lazy frames.

Without validation, the engine executes invocations, binds dataframe and
parameter references, and calls the scheduled merge functions. Missing runtime
bindings and native function or dataframe errors still fail their invocation.
Saved-build integrity, configuration, and backend compatibility checks remain
enabled regardless of this flag.

The engine always stages fragment-producing results for their scheduled merge.
With validation enabled, it checks declared feature input availability before
invoking each non-effect operator and validates raw fragments. Merge results
must always be dataframes with required dimensions and exactly the target's
expected columns. Declared types and key uniqueness are checked with
validation. Vectorize's enriched target-frame type and schema are checked
before publication in either mode; preserving existing values and row order is
checked only with validation enabled.

`InvocationValidator` runs only when validation is enabled. It holds its
backend, runtime state, and invocation directly, and checks inputs in fail-fast
order: foreign
dataframe argument, source reference, source availability, then source features;
other invocation kinds check local or unambiguous cross-profile features.
`FragmentValidator` checks raw invocation results before output projection.
`ColumnsValidator` always checks the vectorize result type and complete
schema, and checks existing values and row order when validation is enabled.
`MainFrameValidator` checks the accumulated dataframe's structure and declared
types of columns already present. Merge-result structural checks and feature
collision checks are mandatory even when runtime validation is disabled;
declared type and key uniqueness checks are enabled by `--validate`.
`MainFrame.merge()` independently guards direct physical assembly calls.

Validation functions emit debug messages when checking a contract or skipping
an inapplicable check. Enable `DEBUG` logging for the `uptimely.engine` logger
to trace these checks. Messages describe attempted checks, not successful
outcomes; violations still fail fast through the normal error path. No
structured validation report is collected.

| Check | Runtime requirement |
| --- | --- |
| Merge result | Every merge returns a dataframe with required dimensions and the complete expected target schema. |
| Outputs | Every declared output feature is projected into the staged fragment. |
| Keys | With validation enabled, complete profile grain keys are unique; dimensionless inputs contain at most one row. |
| Vectorize schema | Every existing target column remains present; only declared output columns may be added. This structural check is mandatory. |
| Vectorize data | With runtime validation enabled, existing values, row count, key identities, and original row order are compared with the accumulated target. |
| Types | Declared dimension and feature types match the returned schema. |
| Feature collisions | Output feature columns do not replace columns already assembled; checked in either mode. |

Checking lazy-frame key uniqueness and comparing vectorize data executes
queries and may repeatedly recompute upstream operations. Enable validation
when debugging or verifying operator contracts; it can add substantial runtime.
Validated vectorize execution materializes its lazy input once and passes a
lazy view of that snapshot to the function. This makes the preservation check
compare the same input observations rather than independently executing an
upstream query whose row order may vary. Without validation, no input snapshot
is collected.
With `validate=False`, the engine still requires a vectorize result dataframe
with all existing columns, all declared outputs, and no undeclared added
columns, but does not prove that existing values or row order are unchanged.
Vectorize publishes the returned frame directly without fragment staging or a
merge invocation. The default merge function enforces one-to-one or
many-to-one key constraints with validation enabled; without validation, those
optional checks are skipped, not deferred to a write or final collection.

User functions, sinks, and explicit `collect()` calls can execute lazy queries
in either mode. Fragment staging and merge result checks may resolve schemas,
including source metadata. Errors during later collection are not reflected in
an already returned engine result. The former `backend.validate_lazy_frames` setting has
been removed; remove it from configuration and use the run flag instead.

Logical types used for validation are:

| Logical type | Meaning |
| --- | --- |
| `string` | Text value. |
| `integer` | Integer value. |
| `float` | Floating-point value. |
| `numeric` | Numeric value. |
| `boolean` | Boolean value. |
| `datetime` | Datetime value, optionally timezone-aware. |
| `date` | Calendar date. |
| `object` | Structured value. |
| `array` | List or array value. |

Types are checked against feature metadata and the root dimension registry;
repeated dimension feature metadata does not override the root type. Values
are not automatically converted. An unknown declared type fails validation,
while an omitted feature type skips that feature's type check.

In either mode, only dimension and declared output columns are merged.
Additional columns returned by a function are ignored, so they cannot replace
other features on the target profile. Other data-producing operations may
change coverage within the target profile's grain.

These runtime checks enforce the declared data contract; they do not verify
that a calculation is analytically correct or prove that arbitrary Python
code is pure. Test calculations directly and add domain-specific assertions
for correctness. The engine does not currently support declared data-quality
rules. Feature types and null values do not imply automatic quality checks.
