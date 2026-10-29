# Spec

**Current spec version: 3**

The spec definition is a single JSON document describing datasets, feature
dependencies, and function bindings. JSON is the shared format used by
analytical declarations and the tools that validate, document, and compile them.

## Document Conventions

The root is one JSON object. Dimensions, entities, datasets, function templates,
features, arguments, and actions use object keys as identifiers. Their IDs are
derived from those keys; serialized action entries also include their `id`.
Identifiers should be stable, lowercase, and descriptive.

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
| `spec_version` | integer | No | `3` | Spec format version; only `3` is supported. |
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
`description`, a list of dimension identifiers, and an ID-keyed object of datasets.
The complete entity dimension key identifies a dataset observation.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | N/A | Display name. |
| `description` | string or null | No | `null` | Explanation of the subject. |
| `dimensions` | array of strings | No | `[]` | Bare identifiers from the root dimension registry. |
| `datasets` | object | No | `{}` | Datasets keyed by identifier describing this subject. |

```json
"entities": {
  "pump": {
    "name": "Pump",
    "dimensions": ["pump_id"]
  }
}
```

## Datasets

Each key under an entity's `datasets` object is a globally unique dataset
identifier, including across different entities. Dataset attributes must not
include `id`. Omitting `datasets` gives an empty object; arrays and `null` are
not accepted.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `description` | string or null | No | `null` | Explanation of the dataset. |
| `row_scope` | object | No | Empty descriptions | Observation grain, filtering, and coverage. |
| `order` | array of objects | No | `[]` | Logical ordering by entity dimensions. |
| `features` | object | No | `{}` | Feature metadata keyed by identifier. |
| `actions` | object | No | `{}` | Function bindings keyed by identifier, unique within this dataset. |

```json
"datasets": {
  "telemetry": {
    "row_scope": {"grain": "One row per pump and timestamp"},
    "order": [
      {"dimension": "$dimensions.timestamp", "direction": "asc"}
    ],
    "actions": {}
  }
}
```

To migrate a version 2 document, rename each dataset's `mappings` object to
`actions` and set `spec_version` to `3`. A version 1 document must first be
migrated to the keyed dataset format introduced in version 2. Rebuild generated
project artifacts after migration. Versions 1 and 2 are not supported.

### Feature and Action Identifiers

Each key under `features` identifies a column's metadata. Each key under
`actions` identifies one function binding, unique within its dataset.
An action identifier names a binding instance, not a reusable function or an
output feature. Multiple actions can invoke the same function with different
arguments. Serialized action entries include an `id` matching their key.

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
Functions implement sorting and grouping themselves. Action context inherits
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
function declares a kind and implementation entrypoint, plus the schema
for its arguments. An action binds a function to concrete arguments and feature
inputs and outputs. When you build the project, each action becomes a step in
the execution plan. The engine runs those steps using the Python
implementations.

Functions are expressed as objects keyed by globally unique function
identifiers.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `kind` | string | Yes | N/A | Function kind: `write`, `read`, `escape`, `conform`, `expand`, `collapse`, or `vectorize`. |
| `returns` | string | Yes | N/A | Return contract: `dataframe` for data-producing kinds or `none` for `write`. |
| `entrypoint` | string | Yes | N/A | Python import reference in `module.path:qualname` form. |
| `validate_signature` | boolean | No | `true` | Whether compilation and documentation inspect the Python signature and check implementation return annotations. |
| `args` | object | No | `{}` | Argument definitions keyed by argument name. |
| `description` | string or null | No | `null` | Explanation of the function. Python declarations default it to the implementation's docstring summary line. |

When `validate_signature` is `true`, the Python entrypoint must declare a
return annotation compatible with `returns`; an unannotated return is invalid.
When it is `false`, compilation and documentation do not load the implementation
or inspect its signature. This disables only implementation signature and
return-annotation checks: declared contracts, binding arguments, feature
dependencies, package provenance, and entrypoint syntax are still validated.
Execution still requires a loadable implementation. Function packages must be
installed in both the build and runtime environments; Uptimely does not install
them or add project paths to `sys.path`. Recorded distribution versions are
provenance only and are not enforced at runtime. Ambiguous installed package
namespaces are reported explicitly.

An entrypoint identifies the implementation associated with a function. Python
imports the module and resolves the callable's qualified name.

```json
"sum_features": {
  "kind": "vectorize",
  "returns": "dataframe",
  "entrypoint": "spec:sum_features",
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

Use kind-oriented function names. Action identifiers and feature names
can differ from the function identifier. Each action binds one function, whose
declared kind determines its analytical role.

### Function kinds

Each function is labeled with exactly one kind. The function's dataframe arguments determine which datasets it consumes. The
table defines the dataframe argument and result counts for each kind:

| Kind | Dataframes in | Results out | Analytical | Dimension change | Purpose |
| --- | ---: | ---: | --- | --- | --- |
| `read` | 0 | 1 | No |  | Read external observations into a dataset. |
| `collapse` | 1 | 1 | Yes | Down | Calculate features from a higher-dimensional foreign dataset. |
| `conform` | 1 | 1 | No | Same | Adapt a same-dimension foreign dataset to the target row scope. |
| `expand` | 1 | 1 | No | Up | Transfer observations from a lower-dimensional foreign dataset. |
| `vectorize` | 1 | 1 | Yes | | Calculate features while preserving observation keys. |
| `write` | 1 | 0 | No |  | Persist or evaluate selected data. |

Data-producing functions return tabular results. Their implementations follow
the kind contract; analytical functions perform their calculations and
grouping but should not perform external I/O.
`read` takes no dataframe argument. Each of `conform`, `collapse`, and
`expand` takes exactly one dataframe argument: its foreign/source dataset. The
target dataset is engine-owned and is not passed to these functions.
`conform` requires the source and target to declare the same dimensions, but
they may belong to different entities. `collapse` requires the source
dimensions to be a strict superset of the target dimensions; `expand` requires
them to be a strict subset. These kinds return fragments for their
declaring (target) dataset; the engine does not pass its accumulated target
frame to the function.

### Arguments

The `args` schema must declare exactly the number of `dataframe` arguments
listed for the function's kind. `vectorize` and `write` receive their
target dataset as their dataframe argument. A dataframe argument represents a
dataset input; other arguments may carry identifiers, features, or external
resource settings. `escape` is uncontrolled and may declare any number of
dataframe arguments.

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
Argument types describe implementation values, not feature dependencies.
Nested expressions such as `object{str: array[string]}` are supported.

## Action Features

An action separates analytical requirements from the implementation binding:

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
selectors. Inputs establish feature dependencies even when not passed as
arguments.
Conversely, passing a feature identifier is not a declaration that its data
must exist. Declare every consumed feature in `inputs`.

Outputs reference the owning dataset's feature registry and are the only
declaration of features produced by an action. Binding arguments may use
feature references to pass identifiers, including output names; those arguments
do not infer inputs or outputs. Entity dimension keys are required in every
returned table, even when omitted from `outputs`.
A write action declares empty outputs and explicitly lists its required inputs.
Data-producing actions require at least one output. Vectorize outputs cannot
redeclare entity dimensions. Collapse must produce at least one non-dimension
feature. There is no binding-level `return` field.

Each `read`, `conform`, `collapse`, or `expand` result is a fragment containing
the target dataset's complete dimension keys and that action's declared
outputs. The engine validates required columns, types, and unique keys, then
assembles same-dataset fragments by key with a full outer join. Partial
coverage is retained; duplicate keys and overlapping feature outputs are
rejected. See the [engine fragment contract](engine.md#fragments) for runtime
details.

### Binding syntax

| Argument reference | Argument type | Value supplied to the implementation |
| --- | --- | --- |
| `$features.<id>.id` | `string` | Feature identifier string. |
| `$dimensions.<id>.id` | `string` | Dimension identifier string. |
| `$datasets.<id>.dimensions.ids` | `array[string]` | Dimension identifiers declared by that dataset's entity. |
| `$datasets.@.dimensions.ids` | `array[string]` | Dimension identifiers declared by the action's target entity. |
| `$datasets.<id>.dataframe` | `dataframe` | Materialized table for that dataset. |
| `$datasets.@.dataframe` | `dataframe` | Current dataset's input-ready table. |
| `$datasets.<id>.id` | `string` | Dataset identifier string. |
| `$features.@.id` | `string` | The sole vectorize output, or sole non-dimension collapse output. |

Unsuffixed references remain supported; their template argument type determines
whether a dataset identifier is resolved to data. Prefer explicit selectors
when writing new declarations. `.id` arguments require `string`, and
`.dataframe` arguments require `dataframe`. Dimension-key selectors require
`array[string]`; their keys must be dimensions of the target and every
referenced dataframe dataset. Use only the reference forms above.

In Python declarations, use `ref.current_dataset().dimensions.ids` or
`ref.dataset("source").dimensions.ids` for the corresponding selector. Key
selectors are explicit binding values; grouping, ordering, and other dimension
references do not implicitly declare matching keys. For a dimensional
operation, pass the selected target keys as its explicit matching-key argument;
the operation's source dataframe remains its only dataframe argument.

### Row Context

`row_context` belongs to the action, not its features or function template.
It describes the greatest required input reach across all calculations in that
action. It does not describe returned rows or alter full-table execution.

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

Document-model validation checks the Spec version, field types, required
values, and rejects unknown fields. Semantic Spec validation checks that
declarations fit together: references and feature dependencies are valid and
unambiguous, function bindings match their argument contracts, kinds obey
their input/output contracts, feature producers are unique, row-context
requirements match their dimensions and ordering, and feature dependencies
are acyclic. When a function's declared return kind and dataframe arguments
conflict with its kind, validation suggests a matching kind where
possible. It never changes the kind automatically; `escape` must be
declared explicitly for intentional uncontrolled work. Spec validation does
not require escape inputs to be produced by a `read` action. A declared
feature without a producing action triggers a warning rather than preventing
the Spec from loading. Validation does not import implementations or inspect
calculated data.

Compilation checks whether a Spec can produce a selected, schedulable plan.
The engine checks runtime values and returned data, including whether declared
feature types match actual columns. For the `validate_spec()` API and its
ordered semantic checks, see the
[Python validation reference](../python/spec/validation.md).

The built-in engine currently accepts Polars `DataFrame` and `LazyFrame`
values only. Other dataframe representations and custom adapters are not part
of this contract.
