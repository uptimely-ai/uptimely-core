# Execution engine

The built-in engine runs the plan in a validated build bundle. It uses the
bundled Spec to find each function and its mapping, calls the Python
implementation, and collects the results. Runtime configuration is supplied
separately.

## Engine settings

Engine settings are supplied to `Engine`, not stored in the Spec
document. The engine implementation decides which configuration values
to use.

Construct an engine with the validated build bundle and required runtime
configuration. The configuration includes backend options and environment-
specific placeholder values under `bind`.

The engine uses the configured `dataframe` string to select a dataframe
backend. The built-in Python engine currently supports `polars`.
Data-producing functions must return a Polars `DataFrame` or `LazyFrame`;
other dataframe representations and custom adapters are not supported.
`evaluation` and `batch_size` are reserved settings: they are
accepted and stored, but do not change evaluation strategy, data access, or
persistence. Do not rely on them to enable lazy execution, batching, or
persistence.

The `engine.json` file has `backend` and `bind` top-level keys:

JSON key | Type | Purpose
--- | --- | ---
`backend` | object | Backend options validated by `EngineBackendConfig`.
`backend.type` | string | Engine type, such as `docker` or `python_venv`.
`backend.definition` | string or `null` | Folder containing configuration files for the engine.
`backend.dataframe` | string | Dataframe backend. The built-in engine currently supports `polars`.
`backend.validate_lazy_frames` | boolean | Defaults to `true`. Set to `false` to skip value checks that would execute a Polars lazy query during engine validation.
`backend.evaluation` | string | Reserved. Values such as `eager`, `lazy`, and `persist` are stored but have no effect on execution.
`backend.batch_size` | integer, `"*"`, or `null` | Reserved. Validates positive integers, `"*"`, or `null`, but does not change how many records are read at a time.
`bind` | object | Runtime values keyed by namespace, object identifier, and attribute for resolving placeholders.

A compiled plan records its backend
claim as `required_backend`; the built-in engine rejects values other than
`polars`. Orchestration is a deployment concern and is not represented in the
Spec document.

## Executing a build bundle

The engine accepts a validated build bundle and executes its compiled portable
plan. It reads dimensions, entities, functions, and datasets from the bundled
`spec.json`, which is loaded as part of the build bundle, and uses the project
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

## Runtime placeholders

A binding argument can hold a literal string of the form
`?<namespace>.<object>.<attribute>`, for example `?storage.telemetry_source.path`.
Unlike `$`-prefixed structural references, the compiler leaves this form
untouched — it carries no graph dependency and is resolved only by the engine,
at execution time, against the engine's `bind` mapping.

`bind` is keyed by namespace, then by object identifier, then by
attribute name. Every operation referencing the same placeholder receives the
configured value.

If a placeholder's namespace, object, or attribute isn't found in
`bind`, the engine raises a `ValueError` for that operation, which
`execute()` records in the returned `ExecutionResult.failures` rather than
raising directly.

Explicit mapping inputs define feature dependencies. Feature identifier
arguments alone do not require those feature values to be materialized.

### Runtime overrides

Runtime configuration substitution is already supported. Supply a different
`bind` mapping when constructing the engine to run the same
compiled plan against dev, test, or prod resources without recompilation.
The plan must already contain placeholders for the values you want to vary.
This does not modify Spec or replace literal arguments, functions,
features, or dependencies.

`EngineConfig` validates the complete engine JSON, including backend settings
and runtime bindings:

```json
{
  "backend": {
    "dataframe": "polars"
  },
  "bind": {
    "storage": {
      "telemetry_source": {
        "path": "/prod/telemetry.json"
      }
    }
  }
}
```

The engine accepts an `EngineConfig` rather than a file path. The CLI and
[MCP server](../tools/ai.md#running-the-server) load this JSON through
`EngineConfig`. Neither interface automatically selects an
environment or merges multiple configuration files. Each supplied mapping must
provide all values required by the invocations being executed; missing values
are errors, not fallbacks to another environment.

## Fragments

A fragment is a subset of a dataset's columns, keyed by the owning entity's
dimensions. It contains those dimension columns and the feature columns declared
as outputs by one data-producing mapping. The engine adds validated fragments
to an accumulated dataset; it does not keep a separate dataset for each
feature.

Data-producing mappings are declared under `read`, `conform`, `expand`, and
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
subset. Each dimensional mapping explicitly supplies its target dimension IDs
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

Fragments in a dataset are combined by the owning entity's complete dimension
key, never by row position. The built-in Polars backend uses a full join,
coalesces key columns, treats null keys as equal, and requires a one-to-one
key relationship. Keys present on only one side are retained, with nulls for
the other fragment's absent values. This supports partial and disjoint
coverage; equal row counts or identical key sets are not required.

Only declared dimension keys may overlap between fragments; overlapping feature
columns are rejected rather than silently discarded. A dimensionless fragment
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

Before invoking a plan invocation, the engine checks that its declared feature
inputs are materialized. Structural references have already been resolved by
the compiler; the engine binds compiled dataframe identifiers to their runtime
frames and substitutes `?`-prefixed placeholders from runtime configuration.
Missing inputs or runtime bindings fail that invocation. For data-producing
mappings, the built-in Polars backend accepts `DataFrame` and `LazyFrame`
results. The engine then validates the returned fragment before merging it:

| Check | Runtime requirement |
| --- | --- |
| Dimensions | Every dimension of the entity is present as a column. |
| Outputs | Every declared output feature is present as a column. |
| Keys | Complete dimension keys are unique; dimensionless datasets contain at most one row. |
| Types | Declared dimension and feature types match the returned schema. |
| Feature collisions | Output feature columns do not replace columns already assembled. |
| Vectorize coverage | The result has exactly the existing dataset key set; row order may differ. |

By default, checking lazy-frame key uniqueness, dimensionless row counts, and
vectorize coverage executes queries. Set `backend.validate_lazy_frames` to
`false` to skip these data-dependent checks for lazy frames. Required-column,
schema/type, and feature-collision checks remain enabled, as do value checks for
eager frames. Polars joins retain `validate="1:1"` and enforce that constraint
when the resulting lazy query is collected. Skipped fragment checks (including
vectorize coverage) are not otherwise deferred or guaranteed. Errors during
later collection are not reflected in an already returned engine result.

This option does not prevent explicit collection by user functions, sinks, or
`PolarsBackend.collect()`, nor does it prevent schema resolution from reading
source metadata. Direct backend value queries such as `row_count()` on a lazy
frame raise an error while implicit lazy execution is disabled.

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

After validation, only dimension and declared output columns are merged.
Additional columns returned by a function are ignored, so they cannot replace
other dataset features. Other data-producing operations may change coverage to
create their target row scope.

These runtime checks enforce the declared data contract; they do not verify
that a calculation is analytically correct or prove that arbitrary Python
code is pure. Test calculations directly and add domain-specific assertions
for correctness. The engine does not currently support declared data-quality
rules. Feature types and null values do not imply automatic quality checks.
