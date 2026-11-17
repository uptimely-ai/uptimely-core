# Spec profiles

## Profiles

### Profile identity and fields

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
| `seed` | string or null | No | `null` | Assembly operator ID initializing the complete profile dataset before accumulation. |
| `grain` | array of objects | No | `[]` | Ordered dimension-resolution references defining row detail. |
| `relations` | array of objects | No | `[]` | Resolutions relating observations to foreign profiles without contributing to row identity. |
| `order` | array of objects | No | `[]` | Logical ordering by selected grain references. |
| `features` | object | No | `{}` | Feature metadata keyed by identifier. |
| `assembly` | object | No | `{}` | Operators keyed by identifier, unique within this profile. |

Selectors not accepted as values.

### Seed operator

When set, `seed` refers to an operator in the profile's assembly. The operator
returns a complete dataframe with the target grain keys, does not have a merge,
and does not consume the target profile's dataframe. It can read a source or
derive the dataset from another profile using a non-nullable dataframe input.
Other fragments merge after the seed.
Profiles without a seed retain the existing accumulation behavior.

### Grain

Each grain reference contains a bare `dimension` identifier and a `resolution`
identifier from that dimension. Together they identify the resolution. A
profile cannot select multiple resolutions of one dimension, and selected
dataframe keys must be distinct. Different
dimensions remain independent axes, so a profile may select separate sales
time and measurement time dimensions. The dimension registry describes what
is available. A profile's grain declares what that profile actually selects.

### Relations

`relations` uses the same dimension and resolution references as `grain`. It
may include several resolutions from one dimension or resolutions from other
dimensions. Relation columns must be distinct from one another, grain keys,
and declared features. Relations do not change which dimensions identify rows
or specify how rows are joined. If a partial dataframe includes relation
columns, the engine keeps them when assembling the result. Declaring a relation
does not calculate or load its values. Explorer labels grain resolutions
**ID** and related-profile columns **Relation**, not features. In this page,
`keys` means both identifiers and relations.

### JSON representation

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

### Feature metadata

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

### Feature fields

| Field | JSON type | Required | Default | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string or null | No | Generated from the feature identifier | Human-readable display name. |
| `type` | string or null | No | `null` | Declared type of the feature. |
| `description` | string or null | No | `null` | Explanation of the feature. |
| `unit` | string or null | No | `null` | Unit of measurement for the feature. |

Selectors not accepted as values.

### Runtime type validation

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

### Feature ownership and producers

A non-dimension feature may belong to only one profile and may have at most one
producing operator. Dimension columns can belong to more than one profile. A
declared feature with no producer causes a warning, not an error.

### Dataframe expectations

Feature and dimension registries describe the columns expected in returned
dataframes. Runtime type checks and dataframe merge behavior are described in
the execution engine guide.
