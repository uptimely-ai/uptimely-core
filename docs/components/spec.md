# Spec

**Current spec version: 0.2.0**

The spec definition is a single JSON document describing datasets, feature
dependencies, and function bindings. JSON is the shared format used by
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

For example, dimensions and entities use their identifiers as object keys:

```json
{
  "dimensions": {
    "pump_id": {"type": "string"}
  },
  "entities": {
    "pump": {"name": "Pump", "dimensions": ["pump_id"]}
  }
}
```

## Document root

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | `null` | Display name. |
| `spec_version` | string | No | `"0.2.0"` | Spec format version; only `0.2.0` is supported. |
| `source` | object | No | `{"name": "manual", "generated": false}` | Authoring metadata. |
| `dimensions` | object | No | `{}` | Dimension definitions keyed by identifier. |
| `functions` | object | No | `{}` | Reusable function definitions keyed by identifier. |
| `entities` | object | No | `{}` | Entity definitions keyed by identifier. |

`spec_version` versions the Spec JSON format, not a particular analytics
project. Increment it when the format changes incompatibly; readers reject
unsupported values.

When supplied, `source` requires `name` (string) and `generated` (boolean).
The default is `{"name": "manual", "generated": false}`. Generated documents
can identify their generator in `name` and set `generated` to `true`.

```json
{
  "name": "Pump analytics",
  "dimensions": {
    "pump_id": {"type": "string"}
  },
  "entities": {}
}
```

## Dimensions

A dimension identifies observations, such as a pump identifier or timestamp.
Each dimension declares `type`, optional `description`, and optional `parent`.
Parents must reference declared dimensions and must not form cycles.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | N/A | Logical key type, such as `string`, `integer`, or `datetime`. |
| `description` | string or null | No | `null` | Explanation of the dimension. |
| `parent` | string or null | No | `null` | Bare identifier of a declared parent dimension. |

Parent metadata describes a hierarchy. It does not automatically add parent
columns to an entity, group calculations, or expand observations.

```json
"dimensions": {
  "pump_id": {"type": "string"},
  "timestamp": {"type": "datetime"}
}
```

## Entities

An entity describes an analytical subject. It has a `name`, optional
`description`, a list of dimension identifiers, and a list of datasets.
The complete entity dimension key identifies a dataset observation.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | N/A | Display name. |
| `description` | string or null | No | `null` | Explanation of the subject. |
| `dimensions` | array of strings | No | `[]` | Bare identifiers from the root dimension registry. |
| `datasets` | array of objects | No | `[]` | Datasets describing this subject. |

```json
"entities": {
  "pump": {
    "name": "Pump",
    "dimensions": ["pump_id"]
  }
}
```

## Datasets

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `id` | string | Yes | N/A | Globally unique dataset identifier. |
| `description` | string or null | No | `null` | Explanation of the dataset. |
| `row_scope` | object | No | Empty descriptions | Observation grain, filtering, and coverage. |
| `order` | array of objects | No | `[]` | Logical ordering by entity dimensions. |
| `features` | object | No | `{}` | Feature metadata keyed by identifier. |
| `mappings` | object | No | `{}` | Function bindings keyed by identifier, unique within this dataset. |

```json
"datasets": [
  {
    "id": "telemetry",
    "row_scope": {"grain": "One row per pump and timestamp"},
    "order": [
      {"dimension": "$dimensions.timestamp", "direction": "asc"}
    ]
  }
]
```

### Feature and Mapping Identifiers

Each key under `features` identifies a column's metadata. Each key under
`mappings` identifies one function binding, unique within its dataset.
A mapping identifier names a binding instance, not a reusable function or an
output feature. Multiple mappings can invoke the same function with different
arguments.

### Row Scope

`row_scope` contains descriptive strings:

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `grain` | No | `""` | What one observation represents. |
| `filtering` | No | `""` | Which observations belong to the dataset. |
| `coverage` | No | `""` | Expected completeness across dimension keys. |

These descriptions do not execute filters or source queries.
Each field must be a string when supplied.

### Logical Order

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `dimension` | string | Yes | N/A | Reference to a dimension of the owning entity. |
| `direction` | string | Yes | N/A | Sort direction: `asc` or `desc`. |

Order keys must be distinct dimensions of the owning entity. Array position
determines key precedence. Omission means no declared order. Null placement,
collation, and ties are not specified.

Order is a logical convention, not a physical sort or partition guarantee.
Functions implement sorting and grouping themselves. Mapping context inherits
dataset order to interpret preceding and following observations.

## Features

A feature is a column describing an entity, whether read from a source or
calculated. Its dataset registry declares the metadata once:

```json
"features": {
  "bearing_temperature": {
    "type": "float",
    "unit": "C"
  },
  "temperature_mean": {
    "type": "float",
    "description": "Trailing temperature mean",
    "unit": "C"
  }
}
```

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `type` | string or null | No | `null` | Logical type of the feature. |
| `description` | string or null | No | `null` | Explanation of the feature. |
| `unit` | string or null | No | `null` | Unit of measurement for the feature. |

The built-in engine supports these feature types:

| Type | Meaning |
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

Declare feature types explicitly: a tabular result's general type does not
describe the types of its individual columns.

Non-dimension feature identifiers must be globally unique and have exactly
one producer. Dimension columns can recur across datasets.

Feature and dimension registries describe the columns expected in tabular
results. Runtime type checks and dataframe merge behavior are described in the
execution engine guide.

## Functions

A function is a logical analytical function definition bound to an implementation. Each
function declares an operation and implementation entrypoint, plus the schema
for its arguments. A mapping binds a function to concrete arguments and feature
inputs and outputs. Compilation turns each mapping into a callable in the
execution plan.

Functions are expressed as objects keyed by globally unique function
identifiers.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `operation` | string | Yes | N/A | Analytical operation performed by the function. |
| `returns` | string | Yes | N/A | Return contract: `dataframe` for data-producing operations or `none` for `write`. |
| `entrypoint` | string | Yes | N/A | Implementation reference resolved by the execution environment. |
| `validate_signature` | boolean | No | `true` | Whether compilation and documentation inspect the Python signature and check implementation return annotations. |
| `args` | object | No | `{}` | Argument definitions keyed by argument name. |
| `description` | string or null | No | `null` | Explanation of the function. |

When `validate_signature` is `true`, the Python entrypoint must declare a
return annotation compatible with `returns`; an unannotated return is invalid.
When it is `false`, compilation and documentation do not load the implementation
or inspect its signature. This disables only implementation signature and
return-annotation checks: declared contracts, binding arguments, feature
dependencies, and entrypoint syntax are still validated. Execution still
requires a loadable implementation.

An entrypoint identifies the implementation associated with a function. Its
resolution is determined by the execution environment. The value below is
symbolic; a concrete runtime defines its accepted entrypoint syntax.

```json
"sum_features": {
  "operation": "vectorize",
  "returns": "dataframe",
  "entrypoint": "spec.sum_features",
  "validate_signature": false,
  "args": {
    "dataset": {"type": "dataframe"},
    "left_feature": {"type": "string"},
    "right_feature": {"type": "string"},
    "output": {"type": "string"}
  }
}
```

Python spec declarations execute during source loading. If an analytical
implementation is unavailable in that environment, declare its entrypoint as a
string and do not import the implementation from the spec declaration itself.

Use operation-oriented function names. Mapping identifiers and feature names
can differ from the function identifier. Each mapping binds one function, whose
declared operation determines its analytical role.

### Operations

Each function is labeled with exactly one operation. The function's inputs determine
which datasets it consumes. The table defines the dataset input and
output counts for each operation:

| Operation | Datasets in | Datasets out | Analytical | Dimension change | Purpose |
| --- | ---: | ---: | --- | --- | --- |
| `read` | 0 | 1 | No |  | Read external observations into a dataset. |
| `collapse` | 1 | 1 | Yes | Down | Calculate features at a coarser grain. |
| `conform` | 2 | 1 | No |  | Adapt observations to the target row scope. |
| `expand` | 2 | 1 | No | Up | Transfer or join observations into target dimensional coverage. |
| `vectorize` | 1 | 1 | Yes | | Calculate features while preserving observation keys. |
| `write` | 1 | 0 | No |  | Persist or evaluate selected data. |

All data-producing functions return tabular data. They perform their own
calculations, grouping, output naming, and scalar broadcasting.
Analytical functions should not perform external I/O.

### Arguments

The `args` schema must declare exactly the number of `dataframe` arguments
listed for the function's operation. A dataframe argument represents a dataset
input; other arguments may carry identifiers, features, or external resource
settings.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | N/A | Argument type expression. |
| `comment` | string or null | No | `null` | Optional explanatory comment. |

Argument definitions are keyed by argument name in the function's `args`
object.

### Argument Types

Common argument type expressions are:

| Type | Meaning |
| --- | --- |
| `string` | String value. |
| `integer` | Integer value. |
| `float` | Floating-point value. |
| `boolean` | Boolean value. |
| `dataframe` | Tabular dataset input. |
| `array` | Collection value. |
| `object` | Dictionary value. |

Homogeneous collections use recursive type expressions:

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
Nested expressions such as `object{str: array[string]}` are supported.

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

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `features` | object | No | Empty lists | Explicit prerequisites and outputs. |
| `features.inputs` | array of strings | No | `[]` | Materialized features required before the call. |
| `features.outputs` | array of strings | No | `[]` | Features produced in the owning dataset. |
| `row_context` | object or null | No | `null` | Surrounding-observation requirements. |
| `binding` | object | Yes | N/A | Function invocation. |
| `binding.function` | string | Yes | N/A | Identifier of the function definition to bind. |
| `binding.args` | object | No | `{}` | Concrete arguments matching the template schema. |

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

### Binding syntax

| Argument reference | Argument type | Value supplied to the implementation |
| --- | --- | --- |
| `$features.<id>.id` | `string` | Feature identifier string. |
| `$dimensions.<id>.id` | `string` | Dimension identifier string. |
| `$datasets.<id>.dataframe` | `dataframe` | Materialized table for that dataset. |
| `$datasets.@.dataframe` | `dataframe` | Current dataset's input-ready table. |
| `$datasets.<id>.id` | `string` | Dataset identifier string. |
| `$features.@.id` | `string` | The sole vectorize output, or sole non-dimension collapse output. |

Unsuffixed references remain supported; their template argument type determines
whether a dataset identifier is resolved to data. Prefer explicit selectors
when writing new declarations. `.id` arguments require `string`, and
`.dataframe` arguments require `dataframe`. Use only the reference forms above.

### Row Context

`row_context` belongs to the mapping, not its features or function template.
It describes the greatest required input reach across all calculations in that
mapping. It does not describe returned rows or alter full-table execution.

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `dimension` | Conditional | N/A | Reference to a declared input dimension; required for `time` or `steps`. |
| `before` | No | `{}` | Required preceding context. |
| `after` | No | `{}` | Required following context. |

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
Functions handle grouping and sorting themselves.

Nonzero directional requirements need dataset order. A time/step dimension must
belong to the input entity and have the matching type. When directional context
requires ordering, that dimension must also occur in the dataset's order.
For collapse, validation uses the inferred source dataset rather than the target.

Fixed durations use these distinct lowercase suffixes:

| Suffix | Unit |
| --- | --- |
| `w` | Weeks (7 days) |
| `d` | Days (24 hours) |
| `h` | Hours |
| `m` | Minutes |
| `s` | Seconds |
| `ms` | Milliseconds |
| `us` | Microseconds |
| `ns` | Nanoseconds |

Durations are nonnegative, contain no whitespace, and have nanosecond or
coarser precision.

An eight-row rolling window including the current row needs seven preceding
rows. An eight-hour window ending two hours ago needs ten hours before.
Declarations must describe actual reach, not merely the window parameter.

## Validation

Spec validation checks document structure and semantic consistency:

- Supported version, field types, required values, and no unknown fields.
- Valid and unambiguous identifiers and references for dimensions, datasets,
  and feature producers.
- Mapping and function operation, input, output, and argument contracts.
- Row-context requirements against input dimensions and dataset order.
- Valid, acyclic feature dependencies.
