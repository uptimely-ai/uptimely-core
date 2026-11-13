# Spec

**Current spec version: 8**

The Spec is a JSON document that describes profiles, feature dependencies, and
the functions used by operators. The same format is used by tools that check,
document, and prepare the declarations for execution.

## Document Conventions

The root is one JSON object. Dimensions, profiles, functions,
features, arguments, and operators use object keys as identifiers. Their IDs
are derived from those keys. Operator entries do not include an `id` field.
Identifiers should be stable, lowercase, and descriptive.

Tables list the fields and values accepted by the current Spec format. A default
is used when a field is omitted, but it does not usually make explicit `null`
valid. Unknown fields cause an error. The JSON has the same meaning regardless
of which tool reads it.

References use field-specific syntax. A field may use a declared ID, a
dimension-resolution pair, or a `$...` selector. Fields that accept selectors
are marked in their schema tables. See [Selectors](#selectors) for their syntax
and examples. For object and array fields, selectors may appear in their values.

For example, dimensions and profiles use their identifiers as object keys:

```json
{
  "dimensions": {
    "machine": {
      "resolutions": {
        "pump": {"key": "pump_id", "type": "string"},
        "fleet": {"key": "fleet_id", "type": "string"}
      }
    },
    "measurement_time": {
      "resolutions": {
        "timestamp": {"key": "timestamp", "type": "datetime"}
      }
    }
  },
  "profiles": {
    "pump_telemetry": {
      "name": "Cooling Pump Telemetry",
      "grain": [
        {"dimension": "machine", "resolution": "pump"},
        {"dimension": "measurement_time", "resolution": "timestamp"}
      ]
    }
  }
}
```

## Document root

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | `null` | Display name. |
| `spec_version` | integer | No | `8` | Spec format version. Only version `8` is accepted. |
| `source` | object | No | `{"name": "manual", "generated": false}` | Information about where the document came from. |
| `dimensions` | object | No | `{}` | Dimension definitions keyed by identifier. |
| `functions` | object | No | `{}` | Reusable function definitions keyed by identifier. |
| `profiles` | object | No | `{}` | Profile definitions keyed by globally unique identifier. |

Selectors not accepted as values.

`spec_version` identifies the Spec JSON format, not a particular analytics
project. Increment it when the format changes in a way that older readers
cannot handle. Documents with another version are rejected.

The Spec defines the workflow. Project configuration supplies values and
settings for each run. These values can change results without changing which
operations run or requiring the workflow to be rebuilt.

| Setting | Where it is set | Rebuild required? |
| --- | --- | --- |
| Spec declarations, including dimensions, functions, profiles, and operators | Spec | Yes |
| Runtime parameters and resource paths | `params` and `paths` in project runtime configuration | No |
| Check returned data during a run | Run option: `uptimely run --validate` or `Engine.run(validate=True)` | No |
| Engine backend | `engine.backend` in project runtime configuration | No, if it matches the backend required by the saved plan |

The saved plan specifies which backend it uses. Choosing a different backend in
project configuration causes an error.

`source` records how the document was authored. Its fields are:

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | Yes, when `source` is supplied | N/A | Identifies the authoring source or generator. |
| `generated` | boolean | Yes, when `source` is supplied | N/A | Indicates whether the document was generated. |

Selectors not accepted as values.

This example shows every document-root field, with one dimension and one
profile. The `functions` object is empty because no reusable functions are
declared.

```json
{
  "name": "Data-center cooling pump analytics",
  "spec_version": 8,
  "source": {"name": "manual", "generated": false},
  "dimensions": {
    "machine": {
      "resolutions": {
        "pump": {"key": "pump_id", "type": "string"}
      }
    }
  },
  "functions": {},
  "profiles": {
    "pump_telemetry": {
      "grain": [{"dimension": "machine", "resolution": "pump"}]
    }
  }
}
```

## Dimensions

A dimension describes one aspect of observations and lists its resolutions.
Each resolution names a dataframe column (`key`), its declared type, and
optionally a parent resolution in the same dimension. Parent links describe a
hierarchy and must not form cycles.

Fields for dimensions:

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `resolutions` | object | Yes | N/A | Available resolutions keyed by resolution identifier. |
| `name` | string or null | No | Generated from the dimension identifier | Human-readable display name. |
| `description` | string or null | No | `null` | Explanation of the dimension. |

Selectors not accepted as values.

Each resolution has the following fields:

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `key` | string | Yes | N/A | Dataframe column used for this resolution. |
| `type` | string | Yes | N/A | Declared key type, such as `string`, `integer`, or `datetime`. |
| `parent` | string or null | No | `null` | Identifier of a parent resolution in this dimension. |
| `name` | string or null | No | `null` | Human-readable resolution label used by Explorer instead of the identifier when provided. |

Selectors not accepted as values.

Resolution IDs are local to their dimension, and the identity of a resolution is
the pair of dimension and resolution IDs. The `parent` field names a resolution
within its containing dimension. A parent link does not add a parent key to a
profile or expand its observations.

## Functions

Each function declaration describes an operation by naming its implementation,
the kind of result it returns, and the arguments it accepts. Operators use
these declarations and supply values, feature inputs, and outputs.

Functions are expressed as objects keyed by globally unique function
identifiers.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | Generated from the function identifier | Human-readable display name. |
| `category` | string or null | No | `null` | Optional descriptive grouping. It does not change how the function is called or what it returns. |
| `returns` | string | Yes | N/A | Result type: `dataframe`, `none`, or `any` when the result is ignored. |
| `entrypoint` | string | Yes | N/A | Reference used to locate the function implementation. |
| `validate_signature` | boolean | No | `true` | Whether to inspect the implementation signature during compilation and in Explorer. |
| `args` | object | No | `{}` | Argument definitions keyed by argument name. |
| `description` | string or null | No | `null` | Explanation of the function. |

Selectors not accepted as values.

When enabled, compilation checks that the implementation accepts the declared
arguments as keywords, has no undeclared required parameters, and that any
available parameter and return annotations are compatible. Explorer inspects
the implementation signature to show its details. Neither check verifies
calculated results. See the [Compiler](compiler.md) page for details.

```json
"sum_features": {
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

### Arguments

The `args` object lists the types of values a function accepts. A dataframe
argument passes a dataframe value. Other arguments may pass identifiers,
feature names, or resource settings. Each dataframe argument must be connected
to a dataset in the operator declaration.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | N/A | Argument type expression. |
| `comment` | string or null | No | `null` | Optional explanatory comment. |

Selectors not accepted as values.

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
| `dataframe` | Dataframe input. |
| `dataframe | null` | Nullable dataframe input, used for a merge's initial dataset. |
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
Argument types describe values passed to a function, not which features it
uses.
Nested expressions such as `object{str: array[string]}` are supported.

## Profiles

A profile describes observations, their dimensions, features, operators, and
optional metadata. Each profile is identified by its globally unique object key. Do not include an
`id` field. Its ordered `grain` selects one resolution per dimension and sets
the dataframe key order. An empty grain means rows have no dimension
keys.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | Generated from the profile identifier | Human-readable display name. |
| `description` | string or null | No | `null` | Explanation of the profile. |
| `category` | string or null | No | `null` | Optional free-form grouping label. |
| `scope` | string or null | No | `null` | Free-form descriptive information. It does not affect validation or execution. |
| `grain` | array of objects | No | `[]` | Ordered dimension-resolution references defining row detail. |
| `relations` | array of objects | No | `[]` | Resolutions relating observations to foreign profiles without contributing to row identity. |
| `order` | array of objects | No | `[]` | Logical ordering by selected grain references. |
| `features` | object | No | `{}` | Feature metadata keyed by identifier. |
| `assembly` | object | No | `{}` | Operators keyed by identifier, unique within this profile. |

Selectors not accepted as values.

Each grain reference contains a bare `dimension` identifier and a `resolution`
identifier from that dimension. Together they identify the resolution. A
profile cannot select multiple resolutions of one dimension, and selected
dataframe keys must be distinct. Different
dimensions remain independent axes, so a profile may select separate sales
time and measurement time dimensions. The dimension registry describes what
is available. A profile's grain declares what that profile actually selects.

`relations` uses the same dimension and resolution references as `grain`. It
may include several resolutions from one dimension or resolutions from other
dimensions. Relation columns must be distinct from one another, grain keys,
and declared features. Relations do not change which dimensions identify rows
or specify how rows are joined. If a partial dataframe includes relation
columns, the engine keeps them when assembling the result. Declaring a relation
does not calculate or load its values. Explorer labels grain resolutions
**ID** and related-profile columns **Relation**, not features. In this page,
`keys` means both identifiers and relations.

In JSON, `grain`, `relations`, and `order` use dimension and resolution IDs
directly:

```json
"dimensions": {
  "machine": {
    "resolutions": {
      "pump": {"key": "pump_id", "type": "string", "parent": "fleet"},
      "fleet": {"key": "fleet_id", "type": "string"}
    }
  },
  "sales_time": {
    "resolutions": {"day": {"key": "sales_date", "type": "datetime"}}
  },
  "measurement_time": {
    "resolutions": {"timestamp": {"key": "timestamp", "type": "datetime"}}
  }
},
"profiles": {
  "pump_telemetry": {
    "grain": [
      {"dimension": "machine", "resolution": "pump"},
      {"dimension": "sales_time", "resolution": "day"},
      {"dimension": "measurement_time", "resolution": "timestamp"}
    ],
    "order": [
      {
        "dimension": "measurement_time",
        "resolution": "timestamp",
        "direction": "asc"
      }
    ]
  },
  "fleet_summary": {
    "grain": [{"dimension": "machine", "resolution": "fleet"}]
  }
}
```

### Scope

`scope` is an optional free-form string for descriptive metadata, for example
an explanation of which observations are intended to belong to the profile.
It is not interpreted: it does not filter observations, check coverage, or
drive operator execution.

!!! info
    Scope may support structural attributes in the future. For example, it
    could include a list of values for a resolution in one of the profile's
    dimensions.

### Order

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `dimension` | string | Yes | N/A | Dimension ID selected by the profile grain. |
| `resolution` | string | Yes | N/A | Resolution ID selected for that dimension. |
| `direction` | string | Yes | N/A | Sort direction: `asc` or `desc`. |

Selectors not accepted as values.

Order references must be distinct members of the profile grain. Array position
sets key precedence. If `order` is omitted, no order is declared. The format
does not specify where null values appear, how text is sorted, or how ties are
handled. Time-based row context requires the selected resolution to have type
`datetime`. Step-based row context requires type `integer`.

Declaring an order does not sort or divide the data. Functions handle sorting
and grouping themselves. Operator context uses the profile's order to interpret
preceding and following observations.

## Features

A feature is a column describing a profile's observations, whether read from a
source or calculated. The profile's `features` object is keyed by feature ID,
with each entry defining metadata for one column. `name` is an optional
human-readable label and defaults to the ID converted from snake or kebab case
to title case:

```json
"features": {
  "bearing_temperature": {
    "name": "Bearing Temperature",
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
| `name` | string or null | No | Generated from the feature identifier | Human-readable display name. |
| `type` | string or null | No | `null` | Declared type of the feature. |
| `description` | string or null | No | `null` | Explanation of the feature. |
| `unit` | string or null | No | `null` | Unit of measurement for the feature. |

Selectors not accepted as values.

When runtime validation is enabled, the built-in engine checks feature columns
against these types:

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

Declare feature types explicitly: a dataframe's general type does not
describe the types of its individual columns.

A non-dimension feature may belong to only one profile and may have at most one
producing operator. Dimension columns can belong to more than one profile. A
declared feature with no producer causes a warning, not an error.

Feature and dimension registries describe the columns expected in returned
dataframes. Runtime type checks and dataframe merge behavior are described in
the execution engine guide.

## Operator

An operator describes the inputs and outputs of one calculation and names the
function that performs it. Each key under the profile's `assembly` object
identifies one operator. Do not include an `id` field. The key names this
calculation, not a reusable function or output feature. Multiple operators can
use the same function with different arguments.

```json
{
  "assembly": {
    "temperature_mean": {
      "interface": {
        "inputs": ["$features.bearing_temperature"],
        "outputs": ["$features.temperature_mean"]
      },
      "row_context": {
        "dimension": "$dimensions.measurement_time",
        "before": {"time": "8h"},
        "after": {"time": "0s"}
      },
      "compute": {
        "function": "rolling_mean",
        "args": {
          "dataset": "$profiles.@.dataset",
          "column": "$features.bearing_temperature.id",
          "window": "8h",
          "output": "$features.temperature_mean.id"
        }
      }
    }
  }
}
```

| Field | JSON type | Selector | Required | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| `interface` | object | No | No | Empty lists | Explicit prerequisites and outputs. |
| `interface.inputs` | array of strings | Yes | No | `[]` | Features that must be available before the function runs. |
| `interface.outputs` | array of strings | Yes | No | `[]` | Features produced in the owning profile. |
| `row_context` | object or null | No | No | `null` | Surrounding-observation requirements. |
| `compute` | object | No | Yes | N/A | Function call. |
| `compute.function` | string | No | Yes | N/A | ID of the function to call. Use the function ID without a selector. |
| `compute.args` | object | Yes | No | `{}` | Values passed to the function. |
| `merge` | object or null | No | No | `null` | Optional function that combines the current dataset with the compute result. |
| `merge.function` | string | No | Yes when `merge` is set | N/A | ID of the function that combines the data. |
| `merge.args` | object | Yes | No | `{}` | Arguments including the current dataset and the compute result. |

### Compute

`compute.args` supplies values to the function named in `compute.function`.
That function may accept at most one dataframe argument. If the operator also
declares a merge, the compute function must return a dataframe. This result is
a partial dataframe, called a fragment. Without a merge, the returned dataframe
becomes the target profile's dataframe. It must include the target keys and the
operator's declared outputs, but it does not need every feature declared for
the profile. Count dataframe arguments in the function declaration, even when
more than one refers to the same profile. If the compute function has a
dataframe argument, it receives the source profile's dataframe.

Input and output lists contain distinct `$features.<id>` references. Inputs
list the features the calculation reads, even when they are not passed as
arguments. Do not list identifiers or relations there. Declare those through
the profile's `grain` and `relations`. Passing a feature name as an argument
does not list it as an input. The `inputs` list describes features needed by
the compute function, not data used by the merge function.

Outputs must name features declared for the profile. They are the only way to
declare which features an operator produces. Passing a feature name as an
argument does not declare it as an input or output. A target dataframe must
include all target dimension keys and the operator's declared outputs. A
column transform of an existing target dataframe must retain its existing
columns.

A write operator has no outputs and lists its required inputs. Other operators
that produce data must declare at least one feature output, except source
readers that provide only profile identifiers or relations. A collapse
operator must produce at least one feature. The function declaration specifies
what kind of result it returns.

When a merge is declared, the compute result is a fragment. It must include the
target keys available in its source profile and the operator's declared
outputs. For an `expand` operation, the fragment may omit target keys that its
source profile does not have. See the [Engine guide](engine.md#datasets-and-fragments)
for details on combining and checking fragments.

Use selectors in `compute.args` only where the argument accepts them. See
[Selectors](#selectors) for supported references and their value types.

### Merge

The merge is optional, but declare it explicitly. Its function must accept
exactly two dataframe arguments, `dataset` and `fragment`. It may also accept
other arguments. Set `dataset` to `$profiles.@.dataset` and `fragment` to
`$operators.@.fragment`. Before the first merge, `dataset` may be null. The
function must return a dataframe containing the accumulated dataset and
fragment columns, with no additional columns. Merge arguments cannot reference
features.

To use the built-in merge, set its function key in the JSON Spec:

```json
"merge": {
  "function": "merge_by_grain",
  "args": {
    "dataset": "$profiles.@.dataset",
    "fragment": "$operators.@.fragment",
    "dataset_identifiers": "$profiles.@.grain.ids"
  }
}
```

The built-in merge matches rows using the target profile's dimension keys.
Custom merge functions may use different rules. See the
[Engine guide](engine.md#fragment-and-merge) for details.

### Row Context

`row_context` belongs to the operator, not its features or function
declaration. It describes how much surrounding input data its calculations
need. It does not change which rows a function returns or limit execution to a
subset of rows.

| Field | JSON type | Selector | Required | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| `dimension` | string | Yes | Conditional | N/A | Reference to a declared input dimension. Required for `time` or `steps`. |
| `before` | object, string, or integer | No | No | `{}` | Required preceding context. A nonnegative integer is a row-count shorthand. |
| `after` | object, string, or integer | No | No | `{}` | Required following context. A nonnegative integer is a row-count shorthand. |

Each direction can be an object with at most one of these measurements, the
string `"unbounded"`, or a nonnegative integer shorthand for a row count. When
both directions use a measurement, they must use the same one:

| Measurement | Allowed bound | Dimension |
| --- | --- | --- |
| `time` | Fixed duration, such as `"8h"`, or `"unbounded"`. | Datetime. |
| `steps` | Nonnegative integer or `"unbounded"`. | Integer. |
| `rows` | Nonnegative integer or `"unbounded"`. | None. Ordering follows the profile order. |

Only fixed time or step windows and row counts are supported. A window cannot
depend on feature values or on a size calculated from the data.

```json
"row_context": {
  "before": {"rows": 1},
  "after": {"rows": 0}
}
```

Omitting `row_context` or setting it to null means the required range is
unspecified. Empty or zero directions mean only the current row is needed. Two
unbounded directions require the whole input and no declared order. One
unbounded direction still requires an order. Functions handle grouping and
sorting themselves.

Nonzero directional requirements need a profile order. A time or step dimension
must belong to the input profile and have the matching type. If the context
requires ordering by that dimension, include it in the profile's `order`. For
operations that remove dimensions, checks use the source profile identified
from the inputs. Other operations use the target profile.

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
coarser precision. A duration may combine units, such as `"1h30m"`, but may
use each unit suffix only once.

An eight-row rolling window including the current row needs seven preceding
rows. An eight-hour window ending two hours ago needs ten hours before.
The declaration must cover the data the calculation actually needs, not just
repeat its window parameter.

## Selectors

Selectors let a field refer to a declared resource, one of its attributes, or
a runtime value. Use them only in fields marked `Yes` in the `Selector` column
of the schema tables. For object and array fields, a selector may appear inside
the value.

Some fields use a selector to identify a resource directly. For example,
`interface.inputs` and `interface.outputs` use feature selectors such as
`$features.temperature_mean`, while `row_context.dimension` uses a dimension
selector such as `$dimensions.measurement_time`. Other fields require a plain
identifier or a structured value instead. For example, `compute.function`
takes a function ID, and `grain` uses a `dimension` and `resolution` pair.

### Function argument selectors

Function arguments can use these structural selectors:

| Argument reference | Argument type | Value passed to the function |
| --- | --- | --- |
| `$features.<id>.id` | `string` | Feature identifier string. |
| `$dimensions.<id>.id` | `string` | Dimension identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.id` | `string` | Resolution identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.key` | `string` | Dataframe key declared for that resolution. |
| `$dimensions.<id>.resolutions.<resolution_id>.type` | `string` | Declared type of that key. |
| `$dimensions.<id>.resolutions.<resolution_id>.parent` | `string` | Parent resolution ID, or `null` when no parent is declared. |
| `$profiles.<id>.grain.ids` | `array[string]` | Dataframe key names selected by that profile's grain. |
| `$profiles.@.grain.ids` | `array[string]` | Dataframe key names selected by the operator's target profile. |
| `$profiles.<id>.dataset` | `dataframe` | Dataframe for that profile. |
| `$profiles.@.dataset` | `dataframe` | Dataframe for the current target profile. |
| `$profiles.<id>.id` | `string` | Profile identifier string. |
| `$features.@.id` | `string` | The operator's feature output ID when it declares exactly one output. |
| `$operators.@.fragment` | `dataframe` | Fragment produced by the compute function for the merge function. |

Use `$profiles.@.dataset` as the merge dataset and `$operators.@.fragment` as
the merge fragment. The fragment selector is accepted only in `merge.args`.

Use the declared argument type that matches the selected value. For example,
`.id` requires `string`, `.dataset` requires `dataframe` (or `dataframe | null`
for the initial merge dataset), and grain-key selectors require
`array[string]`. Grain keys must be selected by the target profile and every
profile whose dataframe is passed to the function. The `.parent` selector must
be declared as `string` and names a resolution in the same dimension, though
it resolves to `null` when no parent is set.

The `@` marker refers to the current target profile in `$profiles.@` and the
current operator in `$features.@` or `$operators.@`. `$features.@.id` is only
available when the operator declares exactly one output.

Compute arguments can also use feature metadata, such as
`$features.<id>.name`. Function arguments can select other resource metadata,
such as `$profiles.<id>.category`, and the current operator's row context
through `$operators.@.row_context.dimension`,
`$operators.@.row_context.before`, and `$operators.@.row_context.after`.
Compute and merge arguments can select runtime values with `$params.<name>` and
`$paths.<name>`. These values come from project runtime configuration and are
resolved during execution. Merge arguments cannot reference features.

Selecting a dimension or resolution does not pass its dataframe key
automatically. Use a key selector or pass the selected dataset keys as an
explicit argument when the function needs them, such as for grouping or
matching rows across dimensions.

## Validation

Spec validation checks the version, field types, required values, and rejects
unknown fields. It checks structural references against declared resources,
function arguments and return rules against their operator roles, row context
against input dimensions and order, and feature requirements for cycles. Each
non-dimension feature may have at most one producer. Declare `returns: "any"`
when the function's result is intentionally ignored. Outputs from an `escape`
operator satisfy feature requirements during validation, but the engine does
not create their data. A declared feature with no producing operator causes a
warning, but does not prevent the Spec from loading. Spec validation does not
import implementations or inspect calculated data. Parameter and path
references are resolved from project configuration during execution.

Compilation checks whether the declared workflow can be run for the selected
profiles. During execution, the engine always checks dataframe types and
required columns. When run validation is enabled with `uptimely run --validate`
or `Engine.run(validate=True)`, it also checks input-feature availability, key
uniqueness, preservation rules, and declared column types.

The built-in engine currently accepts Polars `DataFrame` and `LazyFrame`
values only. It does not accept other dataframe types or custom adapters.
