# Execution Engine

This page describes the built-in engine shipped with Uptimely Core. It is the reference execution implementation for the project, but it is not the only possible engine. Any engine that can read the portable compiled plan and execute its operations according to the plan contract may be used instead. An alternative engine may be implemented in another language or runtime, as long as it respects the portable execution model and the plan's declared backend compatibility.

## Engine configuration

Runtime configuration is supplied to `Engine`, not stored in the Open Analytics specification. The engine implementation decides which configuration values to use.

The built-in Python engine only uses `dataframe` to validate backend
compatibility. `evaluation` and `batch_size` are reserved settings: they are
accepted and stored, but do not change evaluation strategy, data access, or
persistence. Do not rely on them to enable lazy execution, batching, or
persistence.

```python
from uptimely.engine import EngineConfig

config = EngineConfig(
    type="python_venv",
    definition=None,
    dataframe="polars",
    evaluation="eager",
    batch_size=None,
)
```

Property | Data type | Runtime configuration
--- | --- | ---
type | string | Engine type. Eg `docker` or `python_venv`.
definition | string | Folder having configuration files for engine
dataframe | string | Dataframe backend. The built-in engine currently supports `polars`.
evaluation | string | Reserved. Values such as `eager`, `lazy`, and `persist` are stored but have no effect on execution.
batch_size | integer, `"*"`, or `None` | Reserved. Validates positive integers, `"*"`, or `None`, but does not change how many records are read at a time.

`backend` is not a specification or runtime configuration field. A compiled plan records its backend
claim as `required_backend`; the built-in engine rejects values other than `polars`.
Orchestration is a deployment concern and is not represented in the
specification.

## Dataframe backend

The built-in Python engine currently uses columnar DataFrames and supports
Polars `DataFrame` and `LazyFrame` values. Alternative data representations and
processing models, such as Arrow, Beam, and tensor formats, may be explored in
the future; they are not supported by the built-in engine today.

## Executing a compiled plan

The current Python engine is initialized from a compiled portable plan. A
Specification can still be used indirectly by compiling it first or by using the
convenience constructors, but the runtime engine itself primarily works with the
plan object.

```python
specification = Specification.from_json("examples/example_1/_generated/spec/spec.json")
plan = Compiler(
    specification,
    features=["health_signal_normalized"],
).compile()
engine = Engine(plan, config=EngineConfig(dataframe="polars"))
result = engine.execute()
```

`Compiler.features` is optional. The argument names output features produced by
calculations. When provided, it creates a callable-graph subset containing the
required calculations and their input or calculated-feature dependencies.
Engine executes the resulting plan without special subset logic.

An exported plan can be loaded and executed without recompilation:

```python
plan = ExecutionPlan.from_json("_generated/compile/execution_plan.json")
result = Engine(plan).execute()
```

`result` is an `ExecutionResult` containing `datasets`, `calculated_outputs`,
`operation_statuses`, `durations`, `failures`, and `plan_version`.

### Row-context metadata

Operations can carry `row_context` requirements independently of their primitive
arguments. The batch engine does not pass this metadata to functions or use it
to sort, retain rows, or delay output. Future stateful implementations can inspect
the declarations, but must distinguish unknown context from explicit zero
context and account for grouping performed by functions and dependency chains. See
[row context](../../specification/specification.md#row-context) for the contract.

## Runtime placeholders

A binding argument can hold a literal string of the form
`?<namespace>.<object>.<attribute>`, for example `?storage.telemetry_source.path`.
Unlike `$`-prefixed structural references, the compiler leaves this form
untouched — it carries no graph dependency and is resolved only by the engine,
at execution time, against `runtime_resources`:

```python
engine = Engine(
    plan,
    runtime_resources={
        "storage": {
            "telemetry_source": {"path": "test_fixtures/pump_telemetry.json"},
        },
    },
)
```

`runtime_resources` is keyed by namespace, then by object identifier, then by
attribute name. Every operation referencing the same placeholder receives the
value supplied for that resource.

If a placeholder's namespace, object, or attribute isn't found in
`runtime_resources`, the engine raises a `ValueError` for that operation, which
`execute()` records in the returned `ExecutionResult.failures` rather than
raising directly.

Explicit mapping inputs define feature dependencies. Feature identifier
arguments alone do not require those feature values to be materialized.

### Runtime overrides

Runtime resource substitution is already supported. Supply a different
`runtime_resources` mapping when constructing the engine to run the same
compiled plan against dev, test, or prod resources without recompilation.
The plan must already contain placeholders for the values you want to vary.
This does not modify the specification or replace literal arguments, functions,
features, or dependencies.

An environment-specific JSON file can contain the mapping:

```json
{
  "storage": {
    "telemetry_source": {
      "path": "/prod/telemetry.json"
    }
  }
}
```

`Engine` accepts the decoded mapping, not a file path. Load the file in your
application before constructing the engine:

```python
import json
from pathlib import Path

from uptimely.engine import Engine
from uptimely.plan import ExecutionPlan

plan = ExecutionPlan.from_json("_generated/compile/execution_plan.json")
runtime_resources = json.loads(Path("runtime-resources.prod.json").read_text(encoding="utf-8"))
result = Engine(plan, runtime_resources=runtime_resources).execute()
if result.failures:
    raise RuntimeError(f"Execution failed: {result.failures}")
```

The [MCP CLI](../ai/index.md#running-the-server) loads this JSON mapping directly
through `--runtime-resources`. Neither interface automatically selects an
environment or merges multiple configuration files. Each supplied mapping must
provide all resources required by the operations being executed; missing values
are errors, not fallbacks to another environment.

## Engine execution

At runtime, the engine does not keep a separate dataframe for every fragment or
feature in isolation. Instead, it maintains one accumulated dataframe per
`(entity_id, dataset_id)` pair and grows it incrementally as execution proceeds.

Each fragment resource initializes or updates that working dataframe by joining
the fragment's rows on the entity dimensions. Once a fragment is loaded, the
engine materializes the feature columns produced by each vectorize step into the
same accumulated dataset. Every data-producing function returns a dataframe
containing the dimension keys and its declared outputs. The engine merges only
those columns; functions handle grouping, output naming, and literal values.

The built-in compiler and engine do not apply dataset `order` metadata or insert
sorting operations into a plan. Logical order does not change fragment alignment
or guarantee physical row order. Order-sensitive functions must explicitly
declare and implement their ordering inputs.

The loop is: verify materialized inputs, invoke the function, validate its
dataframe keys and output schema, then join the fragment into the dataset.
Vectorize results must preserve the existing dimension-key set. No expression,
series, dictionary, or scalar return adapters are used.

All data-producing mapping categories use the same execution path. Validation
is separate from merging, and runtime outputs are registered only after the
fragment has been successfully merged.

## Write Functions

A write operation is the final node for a dataset in the execution plan. Its
binding uses structural references, which the compiler resolves to IDs. At
runtime the engine uses the function template's mapped primitive types to bind
`dataframe` IDs to physical dataframes; feature and dimension IDs remain
strings for the implementation to interpret. `sink` (like `source`) is
ordinarily a `?storage.<id>.<attribute>` runtime placeholder, resolved against
`runtime_resources` at execution time. The write implementation prepares and
persists the required output.

```json
"args": {
    "sink": "?storage.pump_telemetry_sink.path",
    "dataset": "$datasets.@",
    "features": [
        "$features.bearing_temperature_max",
        "$features.health_signal_normalized"
    ]
}
```

The accumulated dataset contains columns materialized by completed mappings.
Subset plans retain configured dataset sinks; a sink requiring additional
features outside the subset reports an unavailable-input failure rather than
receiving missing data silently.

## Dataset Isolation and Fragment Resources

Vectorize operations consume features only from their own dataset. Fragment
operations may explicitly receive another dataset through a `$datasets.<id>`
reference in their binding arguments and return a new fragment for the target dataset. The
engine never joins features from another dataset implicitly. The specification
declares dataframe-producing resources under `read`, `conform`, `expand`,
and `collapse`.
Each fragment produces a runtime dataframe, includes the entity's dimension columns, and
follows the dataset `row_scope` contract.

With the Polars backend, functions return `pl.DataFrame` or `pl.LazyFrame`.
`calculated_outputs` stores dimension-keyed frames for individual vectorized
outputs. Scalar construction and column naming belong inside the function.

The compiled plan groups independent operations into stages. The current engine
processes those stages and their operations sequentially; another engine may
execute independent operations in parallel while preserving dependency order.

### Fragment Join Behavior

The Polars backend currently combines fragments with a full outer join on all
dimensions declared by the owning entity. It coalesces the join-key columns and
validates a one-to-one relationship:

```python
left.join(
    right,
    on=entity_dimensions,
    how="full",
    coalesce=True,
    validate="1:1",
    nulls_equal=True,
)
```

A full join preserves every dimension key returned by either fragment. This
avoids silently discarding observations when fragment coverage differs. If a
key occurs in only one fragment, columns contributed by the other fragment
contain null values. This is permissive current behavior; it does not prove
that the fragments satisfy the same `row_scope`.

The engine validates structural conditions that can be determined from the
returned dataframes:

- Each fragment is a supported dataframe type.
- Every entity dimension is present as a column.
- Each complete dimension key occurs at most once within a fragment.
- The join has a one-to-one key relationship.

The specification author and fragment implementations remain responsible for
semantic conditions:

- Fragments in one dataset represent the same grain, filtering, and intended
    observation set.
- Missing feature values are represented intentionally. When an observation
    belongs to the dataset but lacks a value, the fragment should normally include
    its dimension key and an explicit null value.
- Fragments with genuinely different row scopes belong in different datasets.
- A `conform` operation must reconcile or narrow data from another dataset in
    the same entity before returning a fragment that conforms to the target
    dataset's row scope.

Vectorize results must match the existing complete key set. Other categories
may change coverage: their omitted keys are preserved by the full join and
exposed as nulls. The engine does not prove declared filtering or coverage.

The function catalog defines these dataframe-producing categories:

| Type | Meaning |
| --- | --- |
| `read` | Reads another dataset from an external source such as a file or database and returns it as a fragment. |
| `collapse` | Returns data grouped by the analytical function, usually at a coarser grain. |
| `expand` | Retrieves another dataset and returns it at expanded dimensional coverage. |
| `conform` | Retrieves another dataset in the same entity and reconciles or narrows it to the target dataset's row scope. |

All dataframe-producing mappings produce data for the dataset that declares
them. For
`conform` and `expand`, the binding usually identifies
another dataset explicitly; the operation function performs the required pull,
transformation, or reconciliation before returning the fragment. The returned
fragment must conform to the target dataset's dimensions and row scope.

Collapse declares explicit input and output feature lists and a normal binding.
Its input features must identify one source dataset, different from the target.
Combining sources requires an explicit expand operation first.
The source dataframe is passed through a dataset argument. The function performs
grouping and returns the target dimension keys alongside its named output
columns. An entity without dimensions has at most one returned observation.

Fragments are combined by the owning entity's complete dimension key. The
engine never combines fragments by row position, so differing row order is safe.
