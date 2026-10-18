# Execution engine

This page describes the built-in Uptimely Core runtime and its execution
contract. It consumes a compiled plan, resolves runtime resources, invokes
functions, and accumulates their tabular results. Other engines can use the same
portable plan format if they implement callable execution and the required
backend.

## Engine settings

Engine settings are supplied to `Engine`, not stored in the Spec
document. The engine implementation decides which configuration values
to use.

The built-in Python engine only uses `dataframe` to validate backend
compatibility. `evaluation` and `batch_size` are reserved settings: they are
accepted and stored, but do not change evaluation strategy, data access, or
persistence. Do not rely on them to enable lazy execution, batching, or
persistence.

The `engine.json` file has `backend` and `bind` top-level keys:

JSON key | Type | Purpose
--- | --- | ---
`backend` | object | Engine settings passed to `EngineConfig`.
`backend.type` | string | Engine type, such as `docker` or `python_venv`.
`backend.definition` | string or `null` | Folder containing configuration files for the engine.
`backend.dataframe` | string | Dataframe backend. The built-in engine currently supports `polars`.
`backend.evaluation` | string | Reserved. Values such as `eager`, `lazy`, and `persist` are stored but have no effect on execution.
`backend.batch_size` | integer, `"*"`, or `null` | Reserved. Validates positive integers, `"*"`, or `null`, but does not change how many records are read at a time.
`bind` | object | Runtime values keyed by namespace, object identifier, and attribute for resolving placeholders.

A compiled plan records its backend
claim as `required_backend`; the built-in engine rejects values other than
`polars`. Orchestration is a deployment concern and is not represented in the
Spec document.

## Executing a compiled plan

The engine executes a compiled portable plan. A plan can be compiled for
selected output features; the compiler includes their prerequisite calculations
and dependencies, so the engine needs no special subset logic. An exported plan
can also be executed without recompilation.

Execution returns datasets, calculated outputs, per-callable statuses and
durations, failures, and the plan version. A failed callable is reported in the
result, and execution stops; callables that did not run are marked skipped.

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

An environment-specific engine JSON file groups backend settings and runtime
bindings under `backend` and `bind`:

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

The engine accepts decoded configuration values rather than a file path. The
[MCP CLI](../tools/ai.md#running-the-server) can load this JSON file through
`--config`, reading backend settings from `backend` and runtime values from
`bind`. Neither interface automatically selects an
environment or merges multiple configuration files. Each supplied mapping must
provide all values required by the callables being executed; missing values
are errors, not fallbacks to another environment.

## Fragments

A fragment is a subset of a dataset's columns, keyed by the owning entity's
dimensions. It contains those dimension columns and the feature columns declared
as outputs by one data-producing mapping. The engine adds validated fragments
to an accumulated dataset; it does not keep a separate dataset for each
feature.

Data-producing mappings are declared under `read`, `conform`, `expand`, and
`collapse`. Each produces a fragment for the dataset that declares it.
`conform` and `expand` can explicitly use another dataset through a
`$datasets.<id>` binding reference; the operation must transform or reconcile
that input before returning a fragment for its target dataset. Vectorize
operations consume features from their own dataset. The engine never joins
another dataset implicitly.

| Type | Meaning |
| --- | --- |
| `read` | Reads data from an external source and returns it as a fragment. |
| `collapse` | Groups input data, usually at a coarser grain, and returns a fragment. |
| `expand` | Uses another dataset to produce a fragment with expanded dimensional coverage. |
| `conform` | Reconciles or narrows data from another dataset in the same entity to the target row scope. |

Collapse inputs must identify one source dataset, distinct from the target.
Combining sources requires an explicit expand operation first. Functions are
responsible for grouping, matching, output names, and constructing literal
values.

The compiled plan groups independent callables into stages. The built-in engine
processes stages and callables sequentially. Dataset `order` metadata does not
sort data or guarantee physical row order; order-sensitive functions must
explicitly declare and implement their ordering inputs.

## Fragment joins and row scope

Fragments in a dataset are combined by the owning entity's complete dimension
key, never by row position. The built-in Polars backend uses a full join,
coalesces key columns, treats null keys as equal, and requires a one-to-one
key relationship. Keys present on only one side are retained, with nulls for
the other fragment's absent values.

The join is intentionally permissive about coverage: it does not prove that
fragments satisfy the dataset's declared grain, filtering, or `row_scope`.
Fragments for one dataset should represent the same intended observations.
Include a key with an explicit null feature value when an observation belongs
to the dataset but its value is missing; put genuinely different row scopes in
separate datasets. A `conform` operation is responsible for reconciling its
source to the target dataset's row scope before returning a fragment.

## Runtime validation

Before invoking a callable, the engine checks that its declared feature inputs
are materialized and resolves its arguments, including runtime placeholders.
Missing inputs or bindings fail that callable. For data-producing mappings,
the built-in Polars backend accepts `DataFrame` and `LazyFrame` results. The
engine then validates the returned fragment before merging it:

| Check | Runtime requirement |
| --- | --- |
| Dimensions | Every dimension of the entity is present as a column. |
| Outputs | Every declared output feature is present as a column. |
| Keys | Complete dimension keys are unique; dimensionless datasets contain at most one row. |
| Types | Declared dimension and feature types match the returned schema. |
| Vectorize coverage | The result has exactly the existing dataset key set; row order may differ. |

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
