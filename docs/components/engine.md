# Execution engine

The built-in engine runs the plan in a validated build bundle. It uses the
bundled Spec to find each function and its action, calls the Python
implementation, and collects the results. Runtime configuration is supplied
separately.

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

Execution returns datasets, calculated outputs, per-invocation statuses and
durations, failures, and the plan version. A failed invocation is reported in
the result, and execution stops; invocations that did not run are marked skipped.

### Row-context metadata

Operations can carry `row_context` requirements independently of their primitive
arguments. The batch engine does not pass this metadata to functions or use it
to sort, retain rows, or delay output. Future stateful implementations can inspect
the declarations, but must distinguish unknown context from explicit zero
context and account for grouping performed by functions and dependency chains.
See the [row context contract](spec.md#row-context).

## Configuration and runtime parameters

Keep framework configuration separate from dataset contents and analytical
inputs. Use it for values that adapt how a workflow runs in this framework, so
the same build can run in different environments without changing its
analytics. Examples include selecting read and write locations and
environment-specific storage or catalog names. Framework-owned settings can
also have defaults, such as the engine's default lazy-frame validation policy.
Other useful controls include backend, validation, materialization, execution
scope, and resource limits when supported by the engine.

Do not put records, feature values, or business thresholds in framework
configuration. Keep data in datasets and analytical inputs as declared feature
inputs in the Spec. Engine options belong in the `engine` configuration or
dedicated CLI options. The `params` map does not set engine options directly;
it supplies scalar values to function bindings. Use it for framework controls
such as a path or source identifier when a read or write function needs that
value, not for dataset or analytical values.

Binding arguments may contain `$params.<name>` references. Each reference
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

In Python authoring, `up.ref.source("telemetry_source")` and
`up.ref.sink("output_path")` create references to the same map. Parameter
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

A fragment is a subset of a dataset's columns, keyed by the owning entity's
dimensions. It contains those dimension columns and the feature columns declared
as outputs by one data-producing action. The engine adds validated fragments
to an accumulated dataset; it does not keep a separate dataset for each
feature.

Data-producing actions are declared under `read`, `conform`, `expand`, and
`collapse`. Each produces a fragment for the dataset that declares it.
`conform`, `expand`, and `collapse` take exactly one foreign/source dataframe
through a `$datasets.<id>.dataframe` binding reference. The engine does not
pass the accumulated target frame to these functions; each function transforms
its foreign input into a fragment for the target dataset. `read` takes no
dataframe argument. Vectorize operations consume features from their own
dataset. The engine never joins another dataset implicitly.

| Type | Meaning |
| --- | --- |
| `read` | Reads data from an external source and returns it as a fragment. |
| `collapse` | Groups input data, usually at a coarser grain, and returns a fragment. |
| `expand` | Uses another dataset to produce a fragment with expanded dimensional coverage. |
| `conform` | Reconciles data from a same-dimension foreign dataset to the target row scope. |

`conform` requires source and target datasets to declare the same dimensions,
but they may belong to different entities. `collapse` requires the source to
have a strict superset of the target dimensions; `expand` requires a strict
subset. Each dimensional action explicitly supplies its target dimension IDs
as matching keys, for example with
`ref.current_dataset().dimensions.ids`. A dimension reference used for
grouping or ordering does not implicitly select a join key. Combining sources
requires an explicit dimensional operation; same-dataset fragment assembly is
not a cross-dataset reconciliation. Functions are responsible for grouping,
matching, output names, and constructing literal values.

The compiled plan groups independent invocations into stages. The built-in engine
processes stages and invocations sequentially. Dataset `order` metadata does not
sort data or guarantee physical row order; order-sensitive functions must
explicitly declare and implement their ordering inputs.

## Fragment joins and row scope

The runtime represents each logical dataset with a physical `MainFrame` holding
its accumulated dataframe and ID column names, without a Dataset or Spec dependency.
Each data-producing invocation contributes a `Fragment`
containing a dataframe and its carried dimension keys. `MainFrame.merge()`
chooses the join from those keys; the backend implements generic dataframe
operations without knowledge of either runtime abstraction.
The invocation executor uses `Fragment.stage()` to load invocation results,
validate them against their invocation's compiled contracts when requested, and project
declared outputs.
It then checks assembly contracts and passes prepared fragments and explicit
retention IDs to the main frame.

Full-grain fragments are combined by the dataset's complete dimension key,
never by row position. The main frame uses a full join, coalesces key columns,
treats null keys as equal, and, with validation enabled, requires a one-to-one
key relationship. Keys present on only one side are retained, with nulls for
the other fragment's absent values. This supports partial and disjoint
coverage; equal row counts or identical key sets are not required.

An `expand` fragment is the exception: it may carry only the dimension keys
its lower-dimensional source can supply. The engine left-joins it onto the
accumulated dataset by those carried keys with a many-to-one relationship,
so each source observation is transferred to every matching target
observation. A fragment with no dimension keys holds at most one row and is
broadcast to all observations; assembling such a fragment requires an already
accumulated target dataset, which the compiler guarantees by running the
dataset's reads first.

With validation enabled, only declared dimension keys may overlap between
fragments; overlapping feature columns are rejected. A dimensionless fragment
represents zero or one global row, and the engine uses an internal
collision-safe join key that is not exposed in the result.

The join is intentionally permissive about coverage: it does not prove that
fragments satisfy the dataset's declared grain, filtering, or `row_scope`.
Fragments for one dataset should represent the same intended observations.
Include a key with an explicit null feature value when an observation belongs
to the dataset but its value is missing; put genuinely different row scopes in
separate datasets. A `conform` operation is responsible for reconciling its
source to the target dataset's row scope before returning a fragment.

## Runtime validation

Per-step runtime validation is opt-in. Use `uptimely run --validate` (also
available as `uptimely engine run --validate`) or `Engine.run(validate=True)`
to check declared feature inputs and returned dataframe contracts at each step.
The same checks apply to eager and lazy frames.

Without validation, the engine executes invocations, binds dataframe and
parameter references, and assembles declared output fragments. Missing runtime
bindings and native function or dataframe errors still fail their invocation.
Saved-build integrity, configuration, and backend compatibility checks remain
enabled regardless of this flag.

With validation enabled, the engine checks declared feature input availability
before invoking each non-effect action, then validates data-producing results
before merging them:

The executor runs validators directly only when validation is enabled.
`InvocationValidator` holds its backend, runtime state, and invocation directly.
Its `validate()` method calls private checks in fail-fast order: foreign
dataframe argument, source reference, source availability, then source features;
other invocation kinds check local or unambiguous cross-dataset features.
`FragmentValidator`
checks raw invocation results before output projection, including the function
kind's row-count and key-preservation contracts. `MainFrameValidator` checks the
accumulated dataframe's structure and declared types of columns already present.
Both hold their validation inputs directly and inherit shared private checks,
called in an explicit, fail-fast order. `MainFrameValidator.validate_merge()`
checks feature collisions separately before joining. Identifier compatibility
and the requirement for an existing broadcast target remain mandatory assembly
guards in `MainFrame.merge()`, even when runtime validation is disabled.

Validation functions emit debug messages when checking a contract or skipping
an inapplicable check. Enable `DEBUG` logging for the `uptimely.engine` logger
to trace these checks. Messages describe attempted checks, not successful
outcomes; violations still fail fast through the normal error path. No
structured validation report is collected.

| Check | Runtime requirement |
| --- | --- |
| Dimensions | Every fragment contains all dimensions declared by its entity; an expand fragment contains the dimensions its source can supply. |
| Outputs | Every declared output feature is present as a column. |
| Keys | Complete dimension keys are unique; dimensionless datasets and fragments contain at most one row. |
| Row count | Vectorize results preserve the accumulated target's row count. Other kinds impose no source-to-result row-count relationship. |
| Types | Declared dimension and feature types match the returned schema. |
| Feature collisions | Output feature columns do not replace columns already assembled. |
| Vectorize coverage | Independently of row count, the result has exactly the accumulated target's dimension-key identities; row order may differ. |

Checking lazy-frame key uniqueness, row counts, and vectorize coverage executes
queries and may repeatedly recompute upstream operations. Enable validation
when debugging or verifying action contracts; it can add substantial runtime.
Validated joins also enforce one-to-one or many-to-one key constraints.
Without validation, joins use unchecked many-to-many semantics and the checks
above are skipped, not deferred to a write or final collection.

User functions, sinks, and explicit `collect()` calls can execute lazy queries
in either mode. Fragment assembly may still resolve schemas, including source
metadata. Errors during later collection are not reflected in an already
returned engine result. The former `backend.validate_lazy_frames` setting has
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
other dataset features. Other data-producing operations may change coverage to
create their target row scope.

These runtime checks enforce the declared data contract; they do not verify
that a calculation is analytically correct or prove that arbitrary Python
code is pure. Test calculations directly and add domain-specific assertions
for correctness. The engine does not currently support declared data-quality
rules. Feature types and null values do not imply automatic quality checks.
