# Spec: Dimensions

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
