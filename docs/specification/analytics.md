# Analytics

Analytics is a single JSON document describing datasets, feature
dependencies, and function bindings. JSON is the canonical contract between
analytical declarations and the tools that validate, document, and compile them.

## Document Conventions

The root is one JSON object. Dimensions, entities, function templates, features,
arguments, and mappings use object keys as identifiers; do not repeat their
`id` inside those entries. Datasets are array entries and require an explicit
`id`. Identifiers should be stable, lowercase, and descriptive.

Tables describe the current parser contract. A default applies when a field is
omitted; it does not generally make explicit `null` valid. Unknown fields are
rejected. The JSON structure defines the same contract regardless of how a
document is authored or consumed.

## Root Object

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `name` | string or null | No; null | Display name. |
| `version` | string | No; `"0.1.0"` | Format version; only `0.1.0` is supported. |
| `source` | object | No; manual source | Authoring metadata. |
| `dimensions` | object | No; `{}` | Dimension definitions keyed by identifier. |
| `functions` | object | No; empty catalog | Reusable operation templates grouped by category. |
| `entities` | object | No; `{}` | Entity definitions keyed by identifier. |

When supplied, `source` requires `name` (string) and `generated` (boolean).
The default is `{"name": "manual", "generated": false}`. Generated documents
can identify their generator in `name` and set `generated` to `true`.

## Dimensions and Entities

A dimension identifies observations, such as a pump identifier or timestamp.
Each dimension declares `type`, optional `description`, and optional `parent`.
Parents must reference declared dimensions and must not form cycles.

An entity describes an analytical subject. It has a `name`, optional
`description`, a list of dimension identifiers, and a list of datasets.
The complete entity dimension key identifies a dataset observation.
Dimensions do not imply calculation partitioning.

### Dimension Fields

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `type` | string | Yes | Logical key type, such as `string`, `integer`, or `datetime`. |
| `description` | string or null | No; null | Explanation of the dimension. |
| `parent` | string or null | No; null | Bare identifier of a declared parent dimension. |

Parent metadata describes a hierarchy. It does not automatically add parent
columns to an entity, group calculations, or expand observations.

### Entity Fields

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `name` | string | Yes | Display name. |
| `description` | string or null | No; null | Explanation of the subject. |
| `dimensions` | array of strings | No; `[]` | Bare identifiers from the root dimension registry. |
| `datasets` | array of objects | No; `[]` | Datasets describing this subject. |

## Datasets

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `id` | string | Yes | Globally unique dataset identifier. |
| `description` | string or null | No; null | Explanation of the dataset. |
| `row_scope` | object | No; empty descriptions | Observation grain, filtering, and coverage. |
| `order` | array of objects | No; `[]` | Logical ordering by entity dimensions. |
| `features` | object | No; `{}` | Feature metadata keyed by identifier. |
| `mappings` | object | No; `{}` | Operations keyed by identifier, unique within this dataset. |

### Feature and Mapping Identifiers

Each key under `features` identifies a column's metadata. Each key under
`mappings` identifies one executable binding, unique within its dataset.
A mapping identifier names a binding instance, not a reusable function or an
output feature. Multiple mappings can invoke the same function with different
arguments. The catalog category of that function determines their operation
kind.

### Row Scope

`row_scope` contains descriptive strings:

- `grain`: what one observation represents.
- `filtering`: which observations belong to the dataset.
- `coverage`: expected completeness across dimension keys.

These descriptions do not execute filters or source queries.
Each field defaults to `""` and must be a string when supplied.

### Logical Order

```json
"order": [
  {"dimension": "$dimensions.timestamp", "direction": "asc"}
]
```

Order keys must be distinct dimensions of the owning entity. Directions are
`asc` or `desc`; array position determines key precedence. Omission means no
declared order. Null placement, collation, and ties are not specified.

Order is a logical convention, not a physical sort or partition guarantee.
Functions implement sorting and grouping themselves. Mapping context inherits
dataset order to interpret preceding and following observations.

## Feature Terminology

A feature is a column describing an entity, whether read from a source or
calculated. Its dataset registry declares the metadata once:

```json
"features": {
  "pump": {"type": "string"},
  "timestamp": {"type": "datetime"},
  "bearing_temperature": {"type": "float", "unit": "C"},
  "temperature_mean": {
    "type": "float",
    "description": "Trailing temperature mean",
    "unit": "C"
  }
}
```

Feature fields are `type`, `description`, and `unit`, all optional.
Each is a string or null and defaults to null.
Types should be declared explicitly: a tabular result's general type does not
describe the types of its individual columns.

Non-dimension feature identifiers must be globally unique and have exactly
one producer. Dimension columns can recur across datasets.

Feature and dimension registries describe the columns expected in tabular
results. Runtime type checks, supported logical types, and dataframe merge
behavior are described in the [execution engine guide](engine.md).

## Functions

Templates declare an `entrypoint`, optional `description` where supported, and
an `args` schema. Each argument definition contains `type` and optional `comment`.

### Function Templates

Each category is an object keyed by function identifier and defaults to `{}`.
All templates require an `entrypoint` string and accept an `args` object,
defaulting to `{}`. Only vectorize templates currently support an optional
`description` string or null; other categories reject that field.

An entrypoint identifies the implementation associated with a template. Its
resolution is determined by the execution environment. The value below is
symbolic; a concrete runtime defines its accepted entrypoint syntax.

```json
"vectorize": {
  "sum_features": {
    "entrypoint": "analytics.sum_features",
    "args": {
      "dataset": {"type": "dataframe"},
      "left_feature": {"type": "string"},
      "right_feature": {"type": "string"},
      "output": {"type": "string"}
    }
  }
}
```

Use operation-oriented function names. Mapping identifiers and feature names
can differ from the template identifier. A bound function must resolve to
exactly one catalog category.

### Operation Types

| Category | Purpose | Analytical role | External I/O | Result |
| --- | --- | --- | --- | --- |
| `read` | Read external observations. | Ingestion. | Reads. | Dataframe fragment. |
| `conform` | Adapt observations to the target row scope. | Row alignment and reconciliation. | None. | Dataframe fragment. |
| `expand` | Transfer or join observations into target dimensional coverage. | Lookup and enrichment. | None. | Dataframe fragment. |
| `collapse` | Calculate features at a coarser grain. | Grouping and aggregation. | None. | Dataframe fragment. |
| `vectorize` | Calculate features while preserving observation keys. | Same-grain calculation. | None. | Dataframe fragment. |
| `write` | Persist or evaluate selected data. | Output evaluation. | May write. | Ignored; no output features. |

All data-producing operations return a table. They perform their own
calculations, grouping, output naming, and scalar broadcasting.
Analytical operations should not perform external I/O.

`vectorize` preserves the current dataset's dimensions and observation keys.
`conform` reconciles row scopes within an entity; `expand` transfers observations
into target dimensional coverage; `collapse` reduces a source to a target grain.
See [modeling patterns](../overview/patterns.md) for join and aggregation examples.

### Argument Definitions

Common argument types include `string`, `integer`, `float`, `boolean`,
`dataframe`, `array`, and `object`. Homogeneous collections use recursive
expressions:

```json
"args": {
  "dataset": {"type": "dataframe"},
  "column": {"type": "string"},
  "window": {"type": "string"},
  "output": {"type": "string"},
  "partition_by": {"type": "array[string]"},
  "limits": {"type": "object{str: float}"}
}
```

Use plain `array` or `object` for heterogeneous or unspecified contents.
Argument types describe implementation values, not data dependencies.
Each argument requires a `type` string; `comment` is an optional string or null.
Nested expressions such as `object{str: array[string]}` are supported.

Structural and semantic checks are described in the
[compiler guide](compiler.md); runtime argument and dataframe behavior is
covered by the [execution engine guide](engine.md). Use typed collections for
nested table references so the engine knows which members to resolve as data.

## Feature Mappings

A mapping separates analytical requirements from the implementation binding:

```json
"temperature_mean": {
  "features": {
    "inputs": ["$features.bearing_temperature"],
    "outputs": ["$features.temperature_mean"]
  },
  "row_context": {
    "dimension": "$dimensions.timestamp",
    "before": {"time": "8h"},
    "after": {"time": "0s"}
  },
  "binding": {
    "function": "rolling_mean",
    "args": {
      "dataset": "$datasets.@.dataframe",
      "column": "$features.bearing_temperature.id",
      "window": "8h",
      "output": "$features.temperature_mean.id"
    }
  }
}
```

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `features` | object | No; empty lists | Explicit prerequisites and outputs. |
| `features.inputs` | array of strings | No; `[]` | Materialized features required before the call. |
| `features.outputs` | array of strings | No; `[]` | Features produced in the owning dataset. |
| `row_context` | object or null | No; null | Surrounding-observation requirements. |
| `binding` | object | Yes | Function invocation. |
| `binding.function` | string | Yes | Template identifier, resolving to exactly one category. |
| `binding.args` | object | No; `{}` | Concrete arguments matching the template schema. |

Input and output lists contain distinct `$features.<id>` references, without
selectors. Inputs establish dependencies even when not passed as arguments.
Conversely, passing a feature identifier is not a declaration that its data
must exist. Declare every consumed feature in `inputs`.

Outputs reference the owning dataset's feature registry. Entity dimension keys
are required in every returned table, even when omitted from `outputs`.
A write mapping declares empty outputs and explicitly lists its required inputs.
Data-producing mappings require at least one output. Vectorize outputs cannot
redeclare entity dimensions. Collapse must produce at least one non-dimension
feature. There is no binding-level `return` field.

### Returned tables

Each mapping declares its outputs and the entity dimensions that identify its
observations. The engine's requirements for returned columns, unique keys,
vectorize key preservation, and fragment alignment are documented in the
[execution engine guide](engine.md#runtime-dataframes). Entity dimensions define
the keys used to align fragments; a conform or expand implementation chooses
its own internal lookup keys and returns rows with the complete target key.
Dimension parent metadata does not choose join keys or perform joins.

### Structural Binding References

| Argument reference | Value supplied to the implementation |
| --- | --- |
| `$features.<id>.id` | Feature identifier string. |
| `$dimensions.<id>.id` | Dimension identifier string. |
| `$datasets.<id>.dataframe` | Materialized table for that dataset. |
| `$datasets.@.dataframe` | Current dataset's input-ready table. |
| `$datasets.<id>.id` | Dataset identifier string; declare a `string` argument. |
| `$features.@.id` | The sole vectorize output, or sole non-dimension collapse output. |

Unsuffixed references remain supported; their template argument type determines
whether a dataset identifier is resolved to data. Prefer explicit selectors
when writing new declarations. `.id` arguments require `string`, and
`.dataframe` arguments require `dataframe`. Use only the reference forms above;
there is no generic JSON-path or attribute traversal. See the
[compiler](compiler.md) and [execution engine](engine.md) guides for how these
references and runtime placeholders are handled.


## Collapse Mappings

Collapse operations transform a source table to the target grain. For example,
a maximum temperature by pump groups source observations by pump and produces
one maximum-temperature value per group.

Declare the operation under `functions.collapse`. Its binding can receive
`$datasets.telemetry.dataframe`, `$features.bearing_temperature.id`, and
`$features.bearing_temperature_max.id`.

Explicit inputs identify one source dataset, different from the target.
At least one input must be a non-dimension feature. Target dimensions must
exist in the source entity. To combine sources, use an expand mapping first.
The function, not the engine, performs grouping and names the returned columns.

## Vectorized Features

Vectorize mappings produce one or more feature columns at the existing dataset
grain. They may receive the current table and return it with added columns, or
return just the dimension keys and output columns.

The result is a table, not an expression or scalar. Literal-valued columns are
part of the operation's result.

## Row Context

`row_context` belongs to the mapping, not its features or function template.
It describes the greatest required input reach across all calculations in that
mapping. It does not describe returned rows or alter full-table execution.

| Field | Meaning |
| --- | --- |
| `dimension` | Required for `time` or `steps`; reference to a declared input dimension. |
| `before` | Required preceding context; defaults to `{}`. |
| `after` | Required following context; defaults to `{}`. |

Each direction is an object containing at most one measurement, or the string
`"unbounded"`. Both directions use the same measurement:

| Measurement | Allowed bound | Dimension |
| --- | --- | --- |
| `time` | Fixed duration, such as `"8h"`, or `"unbounded"`. | Datetime. |
| `steps` | Nonnegative integer or `"unbounded"`. | Integer. |
| `rows` | Nonnegative integer or `"unbounded"`. | None; uses dataset order. |

Only fixed dimension-based windows and row counts are supported. Feature-valued
axes and data-dependent window sizes are not supported.

```json
"row_context": {
  "before": {"rows": 1},
  "after": {"rows": 0}
}
```

An omitted or null context is unknown. Empty or zero directions explicitly mean
current-row-only context. Two unbounded directions require the whole input and
need no order; one unbounded direction still needs logical ordering.
There is no `extent`, mapping-level order, or partition metadata.
Functions handle grouping and sorting themselves.

Nonzero directional requirements need dataset order. A time/step dimension must
belong to the input entity and have the matching type. When directional context
requires ordering, that dimension must also occur in the dataset's order.
For collapse, validation uses the inferred source dataset rather than the target.

Fixed durations use distinct lowercase suffixes `w`, `d`, `h`, `m`, `s`, `ms`,
`us`, and `ns`. They are nonnegative, contain no whitespace, and have nanosecond
or coarser precision. A day is 24 hours; a week is seven days.

An eight-row rolling window including the current row needs seven preceding
rows. An eight-hour window ending two hours ago needs ten hours before.
Declarations must describe actual reach, not merely the window parameter.

The JSON declaration records context requirements explicitly; the compiler
does not infer window semantics from argument names. See the [compiler
guide](compiler.md) for how context metadata is carried into a plan, and the
[execution engine guide](engine.md) for its current runtime behavior.

## Dependencies and validation

The format defines explicit inputs as feature requirements. The compiler guide
describes how these become dependency edges and affect feature-subset plans.

Validation responsibilities are split between the compiler and engine:
structural and semantic checks are described in the [compiler guide](compiler.md),
while runtime checks on materialized inputs and results are described in the
[execution engine guide](engine.md). Neither can establish analytical
correctness or infer hidden function dependencies; test implementations with
their declarations.


## Write Mappings

Writes are ordinary entries under a dataset's `mappings`, not a separate
dataset-level `write` section. They have no feature outputs. For example:

```json
"write_telemetry": {
  "features": {
    "inputs": ["$features.temperature_mean"],
    "outputs": []
  },
  "binding": {
    "function": "write_telemetry",
    "args": {
      "dataset": "$datasets.@.dataframe",
      "columns": ["$features.temperature_mean.id"],
      "sink": "?storage.telemetry_sink.path"
    }
  }
}
```

Register a matching template in `functions.write` with `dataset: dataframe`,
`columns: array[string]`, and `sink: string` argument definitions. Explicit
inputs establish dependencies; the `columns` argument independently identifies
the values to persist. The bound operation defines how they are persisted.
The compiler includes writes according to its subset planning rules; see the
[compiler guide](compiler.md).

## Contract Migration

Replace mapping `features: ["name"]` with
`features: {"inputs": [...], "outputs": ["$features.name"]}`. Move feature-level
context to the producing mapping and remove `extent`. Add dimensions to
time/step context. The JSON key remains `mappings`.

Vectorize and collapse operations produce dimension-keyed tabular results.
Grouping, output naming, and literal construction belong to the operation.
Revalidate analytics and recompile plans; old expression-based plans are
not supported.

## Complete JSON Example

This small analytics document reads two input features and produces their sum for
each observation. Its function entrypoints use the runnable example project so
the document can also be compiled and executed by the test suite.

```json
{
  "name": "Observation totals",
  "version": "0.1.0",
  "dimensions": {
    "id": {
      "type": "integer"
    }
  },
  "functions": {
    "read": {
      "read_observations": {
        "entrypoint": "examples.simple_analytics.functions.functions:read_data"
      }
    },
    "vectorize": {
      "sum_features": {
        "entrypoint": "examples.simple_analytics.functions.functions:sum_features",
        "args": {
          "left_feature": {"type": "string"},
          "right_feature": {"type": "string"},
          "output": {"type": "string"},
          "dataset": {"type": "dataframe"}
        }
      }
    }
  },
  "entities": {
    "observation": {
      "name": "Observation",
      "dimensions": ["id"],
      "datasets": [
        {
          "id": "observations",
          "features": {
            "id": {"type": "integer"},
            "input_1": {"type": "integer"},
            "input_2": {"type": "integer"},
            "total": {"type": "integer"}
          },
          "mappings": {
            "read_observations": {
              "binding": {
                "function": "read_observations"
              },
              "features": {
                "outputs": [
                  "$features.id",
                  "$features.input_1",
                  "$features.input_2"
                ]
              }
            },
            "calculate_total": {
              "binding": {
                "function": "sum_features",
                "args": {
                  "left_feature": "$features.input_1",
                  "right_feature": "$features.input_2",
                  "output": "$features.total",
                  "dataset": "$datasets.@.dataframe"
                }
              },
              "features": {
                "inputs": ["$features.input_1", "$features.input_2"],
                "outputs": ["$features.total"]
              }
            }
          }
        }
      ]
    }
  }
}
```
