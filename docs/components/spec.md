# Spec

**Current spec version: 6**

The spec definition is a single JSON document describing profiles, feature
dependencies, and function bindings. JSON is the shared format used by
analytical declarations and the tools that validate, document, and compile them.

## Document Conventions

The root is one JSON object. Dimensions, profiles, function templates,
features, arguments, and operators use object keys as identifiers. Their IDs
are derived from those keys; operator entries do not include an `id` field.
Identifiers should be stable, lowercase, and descriptive.

Tables describe the current parser contract. A default applies when a field is
omitted; it does not generally make explicit `null` valid. Unknown fields are
rejected. The JSON structure defines the same contract regardless of how a
document is authored or consumed.

Reference syntax is defined by each field; `$...` selectors are not a
universal notation for every link between declarations. Some fields name a
catalog entry directly, some identify a resource by a structured set of IDs,
and selectors are used where the field accepts a value resolved from the
document. Follow the syntax documented for the specific field.

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
      "name": "Pump Telemetry",
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
| `spec_version` | integer | No | `6` | Spec format version; only `6` is supported. |
| `source` | object | No | `{"name": "manual", "generated": false}` | Authoring metadata. |
| `options` | object | No | `{"merge": "auto"}` | Build-time interpretation options. |
| `dimensions` | object | No | `{}` | Dimension definitions keyed by identifier. |
| `functions` | object | No | `{}` | Reusable function definitions keyed by identifier. |
| `profiles` | object | No | `{}` | Profile definitions keyed by globally unique identifier. |

`spec_version` versions the Spec JSON format, not a particular analytics
project. Increment it when the format changes incompatibly; readers reject
unsupported values.

When supplied, `source` requires `name` (string) and `generated` (boolean).
The default is `{"name": "manual", "generated": false}`. Generated documents
can identify their generator in `name` and set `generated` to `true`.

`options.merge` controls how fragment-producing operators obtain merge
bindings. It is either `auto` (the default) or `explicit`; see
[Merge bindings](#merge-bindings).

| Option | JSON type | Default | Meaning |
| --- | --- | --- | --- |
| `options.merge` | string | `"auto"` | Use automatic merge bindings (`"auto"`) or require explicit bindings (`"explicit"`). |

```json
{
  "name": "Pump analytics",
  "dimensions": {
    "machine": {
      "resolutions": {
        "pump": {"key": "pump_id", "type": "string"}
      }
    }
  },
  "profiles": {
    "pump_telemetry": {
      "grain": [{"dimension": "machine", "resolution": "pump"}]
    }
  }
}
```

## Dimensions

A dimension identifies an observation axis and declares one or more keyed
resolutions. Each resolution names a dataframe `key`, its logical `type`, and
optionally a parent resolution from the same dimension. Parent links describe
hierarchy and must not form cycles.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `resolutions` | object | Yes | N/A | Available resolutions keyed by resolution identifier. |
| `name` | string or null | No | Generated from the dimension identifier | Human-readable display name. |
| `description` | string or null | No | `null` | Explanation of the dimension. |

Each resolution has the following fields:

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `key` | string | Yes | N/A | Dataframe column used for this resolution. |
| `type` | string | Yes | N/A | Logical key type, such as `string`, `integer`, or `datetime`. |
| `parent` | string or null | No | `null` | Identifier of a parent resolution in this dimension. |

Resolution IDs are local to their dimension; the identity of a resolution is
the pair of dimension and resolution IDs. The `parent` field names a resolution
within its containing dimension, so it uses that resolution's bare ID rather
than a selector. A parent link does not add a parent key to a profile or expand
its observations.

## Profiles

A profile describes observations, their dimensions, features, operators, and
optional metadata. Profiles are top-level and identified by a globally unique
object key; attributes must not include `id`. Its ordered `grain` selects one
resolution per dimension and defines the dataframe key order. An empty grain
represents a dimensionless profile.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | Generated from the profile identifier | Human-readable display name. |
| `description` | string or null | No | `null` | Explanation of the profile. |
| `category` | string or null | No | `null` | Optional free-form grouping label. |
| `scope` | string or null | No | `null` | Free-form descriptive metadata; it does not affect semantic validation or execution. |
| `grain` | array of objects | No | `[]` | Ordered dimension-resolution references defining row detail. |
| `order` | array of objects | No | `[]` | Logical ordering by selected grain references. |
| `features` | object | No | `{}` | Feature metadata keyed by identifier. |
| `assembly` | object | No | `{}` | Operators keyed by identifier, unique within this profile. |

Each grain reference contains a bare `dimension` identifier and a `resolution`
identifier from that dimension. Together they identify the resolution; neither
value uses selector syntax. A profile cannot select multiple resolutions of
one dimension, and selected dataframe keys must be distinct. Different
dimensions remain independent axes, so a profile may select separate sales
time and measurement time dimensions. The dimension registry describes what
is available; a profile's grain declares what that profile actually selects.

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

Version 4 replaced the entity-owned `datasets` structure with top-level
`profiles`. Dimensions declare available resolutions; each profile must select
its own grain explicitly. Entity-owned dimensions and descriptive
`row_scope.grain` text do not determine the selected grain. The optional
`category` and `scope` fields do not affect semantic validation or execution.
Rebuild generated project artifacts after migration; version 3 is not supported.

## Migrating from spec version 3

Version 3 documents are rejected rather than parsed with compatibility rules.
Migrate the source document, then rebuild its execution plan and Explorer
snapshot:

1. Move each entity-owned dataset to the top-level `profiles` object and give
   each profile a globally unique ID. Remove the `entities` object and entity
   references.
2. Replace inherited entity dimensions with top-level dimension declarations.
   Declare each available keyed resolution under its dimension, including its
   dataframe `key`, logical `type`, and any same-dimension `parent`.
3. Add an explicit `grain` to every profile that needs dimension keys. Each
   entry selects a `dimension` and one of its `resolutions`; do not infer a
   profile grain from an entity or from descriptive text. Use `[]` for a
   dimensionless profile.
4. Replace `row_scope` with an optional descriptive string `scope`. It is not
   executable and does not filter rows or validate coverage. If `row_scope`
   previously held grain or filtering rules, move those requirements into
   explicit profile grains or application logic as appropriate.
5. Change dataset selectors to profile selectors, such as
   `$profiles.<id>.grain.ids` or `$profiles.@.grain.ids`, then export version 6
   and rebuild all generated artifacts.

## Migrating from spec version 4

Version 4 documents are rejected rather than parsed with compatibility rules.
Update every profile's `actions` object to `assembly`. Within each operator,
rename `binding` to `compute` and the operator-level `features` object to
`interface`. Remove the operator's `id` field; its ID is the key in `assembly`.
Set `spec_version` to `6` (the default when omitted), then rebuild generated
execution plans and Explorer snapshots.

## Migrating from spec version 5

Version 5 documents are rejected rather than parsed with compatibility rules.
Set `spec_version` to `6`, add an `options` object if non-default merge
behavior is required, and rebuild generated plans and Explorer snapshots.
Operators may now declare `merge` beside `compute`; version 6 does not infer
custom merge behavior from older operator or assembly fields.

### Feature and Operator Identifiers

Each key under `features` identifies a column's metadata. Each key under
`assembly` identifies one operator, unique within its profile. An operator
identifier names a compute instance, not a reusable function or an output
feature. Multiple operators can invoke the same function with different
arguments. The key supplies the operator ID; an `id` attribute is rejected.

### Scope

`scope` is an optional free-form string for descriptive metadata, for example
an explanation of which observations are intended to belong to the profile.
It is not interpreted: it does not filter observations, check coverage, or
drive operator execution.

The former `row_scope` object is not accepted.

### Logical Order

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `dimension` | string | Yes | N/A | Dimension ID selected by the profile grain. |
| `resolution` | string | Yes | N/A | Resolution ID selected for that dimension. |
| `direction` | string | Yes | N/A | Sort direction: `asc` or `desc`. |

Order references must be distinct members of the profile grain. Array position
determines key precedence. Omission means no declared order. Null placement,
collation, and ties are not specified. Time-based row context requires the
selected resolution to have type `datetime`; step-based row context requires
type `integer`.

Order is a logical convention, not a physical sort or partition guarantee.
Functions implement sorting and grouping themselves. Operator context inherits
profile order to interpret preceding and following observations.

## Features

A feature is a column describing a profile's observations, whether read from a
source or calculated. Its profile registry declares the metadata once. The registry key
is the feature ID; `name` is an optional human-readable label and defaults to
the ID converted from snake or kebab case to title case:

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
one producer. Dimension columns can recur across profiles.

Feature and dimension registries describe the columns expected in tabular
results. Runtime type checks and dataframe merge behavior are described in the
execution engine guide.

## Functions

A function is a logical analytical function definition bound to an implementation. Each
function declares a kind and implementation entrypoint, plus the schema
for its arguments. An operator binds a function to concrete arguments and feature
inputs and outputs. When you build the project, each operator becomes a step in
the execution plan. The engine runs those steps using the Python
implementations.

Functions are expressed as objects keyed by globally unique function
identifiers.

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | Generated from the function identifier | Human-readable display name. |
| `kind` | string | Yes | N/A | Function kind: `write`, `read`, `escape`, `conform`, `expand`, `collapse`, `vectorize`, or `merge`. |
| `returns` | string | Yes | N/A | Return contract: `dataframe` for data-producing kinds, `none` for `write`, or `any` for `escape`. |
| `entrypoint` | string | Yes | N/A | Python import reference in `module.path:qualname` form. |
| `validate_signature` | boolean | No | `true` | Whether compilation and documentation inspect the Python signature and check call compatibility and supported annotations. |
| `args` | object | No | `{}` | Argument definitions keyed by argument name. |
| `description` | string or null | No | `null` | Explanation of the function. Python declarations default it to the implementation's docstring summary line. |

When `validate_signature` is `true`, the Python entrypoint is checked for
keyword-call compatibility with declared arguments, undeclared required
parameters, positional-only parameters, and supported annotation
contradictions. Annotations are optional; a known incompatible annotation is
invalid. When it is `false`, compilation and documentation do not inspect the
callable signature. This disables only implementation signature checks:
declared contracts, binding arguments, feature dependencies, package
provenance, and entrypoint syntax are still validated.
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

Use kind-oriented function names. Operator identifiers and feature names
can differ from the function identifier. Each operator binds one function, whose
declared kind determines its analytical role.

### Function kinds

Each function is labeled with exactly one kind. The function's dataframe
arguments determine which profiles it consumes. The table defines the dataframe
argument and feature-output counts for each kind:

| Kind | Dataframes in | Results out | Analytical | Dimension change | Purpose |
| --- | ---: | ---: | --- | --- | --- |
| `read` | 0 | 1 | No |  | Read external observations into a profile. |
| `collapse` | 1 | 1 | Yes | Down | Calculate features from a higher-dimensional source profile. |
| `conform` | 1 | 1 | No | Same | Adapt a same-dimension source profile to the target profile's rows. |
| `expand` | 1 | 1 | No | Up | Transfer observations from a lower-dimensional source profile. |
| `vectorize` | 1 | 1 | Yes | | Calculate features while preserving observation keys. |
| `merge` | 2 | 1 | No | Same | Combine the nullable current target and one staged fragment into a complete target dataframe. |
| `write` | 1 | 0 | No |  | Persist or evaluate selected data. |
| `escape` | Any explicit arguments | 0 | No |  | Perform uncontrolled work outside the declared feature workflow with logical feature dependencies. |

Data-producing functions return tabular results. Their implementations follow
the kind contract; analytical functions perform their calculations and
grouping but should not perform external I/O.
`read` takes no dataframe argument. Each of `conform`, `collapse`, and
`expand` takes exactly one dataframe argument: its foreign/source dataset. The
target dataset is engine-owned and is not passed to these functions.
`conform` requires the source and target to declare the same dimensions, but
they may belong to different profiles. `collapse` requires the source
dimensions to be a strict superset of the target dimensions; `expand` requires
them to be a strict subset. These kinds return fragments for their
declaring (target) dataset; the engine does not pass its accumulated target
frame to the function.
Escape operators may declare feature inputs, outputs, both, or neither. These
declarations define logical feature dependencies and invocation ordering; they
do not themselves transfer dataframes to or from the escape function. An
escape function may receive dataframes through explicitly declared dataframe
arguments, subject to the normal argument-binding rules; feature declarations
do not implicitly bind a dataframe. Its return value is ignored, so declared
outputs are not materialized as dataset columns. A downstream dataframe operator
that needs an escape output will fail at runtime unless that feature is
independently available in its dataframe.
Merge functions take exactly two dataframe arguments: `target` and `fragment`.
The target argument has type `dataframe | null`; it is bound to the current
profile dataframe and is null when no target has yet been initialized. The
fragment argument is bound to the staged fragment for its own operator. A
merge function returns the complete accumulated target dataframe and does not
declare feature outputs.

### Arguments

The `args` schema must declare the number of `dataframe` arguments required by
the function's kind. `vectorize` and `write` receive their target dataset as
their dataframe argument. A dataframe argument represents a dataset input;
other arguments may carry identifiers, features, or external resource
settings. `escape` may declare any number of dataframe arguments. Each must be
explicitly bound to a dataset; the engine does not implicitly pass the
operator's accumulated dataframe.

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
| `dataframe | null` | Nullable tabular input, used for a merge's initial target. |
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

## Operator Interface and Compute

An operator separates analytical requirements from its computation:

```json
{
  "assembly": {
    "temperature_mean": {
      "interface": {
        "inputs": ["$features.bearing_temperature"],
        "outputs": ["$features.temperature_mean"]
      },
      "row_context": {
        "dimension": "$dimensions.timestamp",
        "before": {"time": "8h"},
        "after": {"time": "0s"}
      },
      "compute": {
        "function": "rolling_mean",
        "args": {
          "dataset": "$profiles.@.dataframe",
          "column": "$features.bearing_temperature.id",
          "window": "8h",
          "output": "$features.temperature_mean.id"
        }
      }
    }
  }
}
```

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `interface` | object | No | Empty lists | Explicit prerequisites and outputs. |
| `interface.inputs` | array of strings | No | `[]` | Materialized features required before the call. |
| `interface.outputs` | array of strings | No | `[]` | Features produced in the owning profile. |
| `row_context` | object or null | No | `null` | Surrounding-observation requirements. |
| `compute` | object | Yes | N/A | Function invocation. |
| `compute.function` | string | Yes | N/A | Function-catalog key identifying the definition to invoke; use the bare function ID, not a `$functions` selector. |
| `compute.args` | object | No | `{}` | Concrete arguments matching the template schema. |
| `merge` | object or null | No | `null` | Optional merge function invocation for a staged fragment. |
| `merge.function` | string | Yes when `merge` is set | N/A | Function-catalog key for a function of kind `merge`. |
| `merge.args` | object | No | `{}` | Arguments including the current target and this operator's staged fragment. |

Input and output lists contain distinct `$features.<id>` references, without
selectors. Inputs establish feature dependencies even when not passed as
arguments.
Conversely, passing a feature identifier is not a declaration that its data
must exist. Declare every consumed feature in `inputs`.

Outputs reference the owning profile's feature registry and are the only
declaration of features produced by an operator. Compute arguments may use
feature references to pass identifiers, including output names; those arguments
do not infer inputs or outputs. Profile dimension keys are required in every
returned table, even when omitted from `outputs`.
A write operator declares empty outputs and explicitly lists its required inputs.
Data-producing operators require at least one output. Vectorize outputs cannot
redeclare profile dimensions. Collapse must produce at least one non-dimension
feature. There is no binding-level `return` field.

Each `read`, `conform`, `collapse`, or `expand` result is a fragment containing
the target dataset's complete dimension keys and that operator's declared
outputs. An `expand` fragment may omit dimension keys its lower-dimensional
source cannot supply; the engine left-joins it onto the accumulated dataset by
the keys it carries. The engine validates required columns, types, and unique
keys, then
assembles same-profile fragments by key with a full outer join. Partial
coverage is retained; duplicate keys and overlapping feature outputs are
rejected. See the [engine fragment contract](engine.md#fragments) for runtime
details.

### Merge bindings

When declared, `merge.args.target` must be `$profiles.@.dataframe` and
`merge.args.fragment` must be `$operators.@.fragment`. The target is nullable
for the first merge. Python declarations use `ref.data()` and `ref.fragment()`.
Merge bindings cannot reference features; assembly
uses the target profile's declared dimensions to determine join keys.
`interface.inputs` declares compute dependencies only.

### Compute syntax

| Argument reference | Argument type | Value supplied to the implementation |
| --- | --- | --- |
| `$features.<id>.id` | `string` | Feature identifier string. |
| `$dimensions.<id>.id` | `string` | Dimension identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.id` | `string` | Resolution identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.key` | `string` | Dataframe key declared for that resolution. |
| `$dimensions.<id>.resolutions.<resolution_id>.type` | `string` | Logical key type declared for that resolution. |
| `$dimensions.<id>.resolutions.<resolution_id>.parent` | `string` or `null` | Parent resolution ID, if declared. |
| `$profiles.<id>.grain.ids` | `array[string]` | Dataframe key names selected by that profile's grain. |
| `$profiles.@.grain.ids` | `array[string]` | Dataframe key names selected by the operator's target profile. |
| `$profiles.<id>.dataframe` | `dataframe` | Materialized table for that profile. |
| `$profiles.@.dataframe` | `dataframe` | Current profile's input-ready table. |
| `$profiles.<id>.id` | `string` | Profile identifier string. |
| `$features.@.id` | `string` | The sole vectorize output, or sole non-dimension collapse output. |

These selectors apply to compute and merge argument values; they are not a general
replacement for the references elsewhere in the document. For example,
`compute.function` uses a function-catalog key, grain uses a
`dimension`/`resolution` pair, and a resolution's `parent` uses a bare
resolution ID scoped to its dimension. Compute arguments can select resolution
metadata with `$dimensions.<id>.resolutions.<resolution_id>.<property>`;
`row_context.dimension` accepts `$dimensions.<id>` as its dimension reference.

Unsuffixed references remain supported; their template argument type determines
whether a profile identifier is resolved to data. Prefer explicit selectors
when writing new declarations. `.id` arguments require `string`, and
`.dataframe` arguments require `dataframe`. Grain-key selectors require
`array[string]`; their keys must be selected by the target and every referenced
dataframe profile. Use only the listed forms for compute arguments.

Merge arguments additionally support `$operators.@.fragment`, which supplies
the current operator's staged fragment as a dataframe. `$profiles.@.dataframe`
in a merge binding supplies the current target, or null before initialization.

In Python declarations, use `ref.profile().grain.ids` or
`ref.profile("source").grain.ids` for the corresponding selector. Grain-key
selectors are explicit binding values; grouping, ordering, and other dimension
references do not implicitly declare matching keys. For a dimensional
operation, pass the selected target keys as its explicit matching-key argument;
the operation's source dataframe remains its only dataframe argument.

### Row Context

`row_context` belongs to the operator, not its features or function template.
It describes the greatest required input reach across all calculations in that
operator. It does not describe returned rows or alter full-table execution.

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
belong to the input profile and have the matching type. When directional context
requires ordering, that dimension must also occur in the dataset's order.
For dimension-removing operations, validation uses the inferred source dataset
rather than the target. Other operations use the target dataset.

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
not require escape inputs to be produced by a `read` operator. Escape outputs
count as logical feature producers for dependency validation, but are not
materialized by the engine. A declared feature without a producing operator
triggers a warning rather than preventing the Spec from loading. Validation
does not import implementations or inspect calculated data.

Compilation checks whether a Spec can produce a selected, schedulable plan.
The engine checks runtime values and returned data, including whether declared
feature types match actual columns. For the `validate_spec()` API and its
ordered semantic checks, see the
[Python validation reference](../python/spec/validation.md).

The built-in engine currently accepts Polars `DataFrame` and `LazyFrame`
values only. Other dataframe representations and custom adapters are not part
of this contract.
