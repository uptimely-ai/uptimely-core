# Spec JSON {#spec}

**Current spec version: 9**

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
are marked in their schema tables. See [Selectors](selectors.md#selectors) for their syntax
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
| `spec_version` | integer | No | `9` | Spec format version. Only version `9` is accepted. |
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
  "spec_version": 9,
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
