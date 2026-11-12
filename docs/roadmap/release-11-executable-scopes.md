# Release 11: Reusable profile filters and action-driven row scopes

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Executable scopes

Turn profile scope from descriptive text into reusable, executable row
selection while keeping resolution (row detail) distinct from scope (included
rows).

**Prerequisites:** Specification model migration; Frame adapter contracts.

For example, a profile can use machine/minute resolution while its scope selects
machines by product category and limits the measurement-time range. A reusable
scope can declare filters directly or compute them through an action. This
illustrative JSON uses the proposed profile terminology; exact reference
syntax is established by the specification-contract work above.

```json
{
  "dimensions": {
    "operating_unit": {
      "type": "hierarchy",
      "resolutions": ["fleet", "product_category", "machine"]
    },
    "measurement_time": {
      "type": "datetime",
      "resolutions": ["day", "hour", "minute"]
    }
  },
  "scopes": {
    "categories_a_and_b": {
      "name": "Machines in product categories A and B",
      "filters": {
        "product_category": {"in": ["A", "B"]},
        "measurement_timestamp": {
          "range": {
            "gte": "2026-01-01T00:00:00Z",
            "lt": "2026-02-01T00:00:00Z"
          }
        }
      }
    },
    "custom_north_scope": {
      "name": "Custom North operations scope",
      "action": {
        "function": "$functions.select_north_scope",
        "args": {}
      }
    }
  },
  "profiles": {
    "machine_minute": {
      "grain": [
        "$dimensions.operating_unit.resolutions.machine",
        "$dimensions.measurement_time.resolutions.minute"
      ],
      "scope": "$scopes.categories_a_and_b"
    },
    "north_hourly": {
      "grain": [
        "$dimensions.operating_unit.resolutions.product_category",
        "$dimensions.measurement_time.resolutions.hour"
      ],
      "scope": "$scopes.custom_north_scope"
    }
  }
}
```

An action returns a `filters` mapping in the same form as the static scope.
For example, it could return `{"region": {"in": ["North"]}}`; it need not
enumerate every matching profile key. The filter column names and dimension
reference syntax above are illustrative, not a finalized schema contract.

The corresponding Python authoring API could use declarative `Scope` classes:

```python
class CategoriesAAndB(Scope):
    name = "Machines in product categories A and B"
    filters = {
        "product_category": {"in": ["A", "B"]},
        "measurement_timestamp": {
            "range": {
                "gte": "2026-01-01T00:00:00Z",
                "lt": "2026-02-01T00:00:00Z",
            }
        },
    }


class CustomNorthScope(Scope):
    name = "Custom North operations scope"
    action = {
        "function": "functions.select_north_scope",
        "args": {},
    }
```

This class-based syntax is illustrative; the authoring contract should define
whether scope declarations are classes, instances, or both, and how action
references are expressed.

| title | breaking | description |
|---|---|---|
| Define reusable scope declarations and filter semantics | Yes | Replace descriptive profile scope text with references to reusable named scopes. Define each scope's `name` and exactly one of static `filters` or an `action`; define filter keys as dataset columns and the supported list and range forms, including empty selections, null handling, type compatibility, bound inclusivity, and how multiple filters combine. Define whether filters may refer to dimensions, features, or other columns, and how a scope can express custom reusable logic that is not a simple dimension/feature selection. Specify how a scope is interpreted at the profile's grain and resolution. |
| Validate and normalize static scope filters | No | Validate scope references, filter structure, column references, value types, range bounds, and operator semantics against profile schemas and grain. Normalize valid filters into a deterministic internal representation and report errors with scope, profile, column, and source-path context. Do not silently ignore unsupported or inapplicable filters. |
| Define and validate scope action contracts | No | Allow a scope to use an `action` bound to reusable project logic. Specify its arguments, dependencies, execution phase, purity and I/O expectations, and exact return contract. Require action-produced selections to use the same filter representation as static scopes, with an explicit extension point or diagnostic for custom selections that cannot be represented by lists or ranges. Validate bindings and return values without treating scope output as feature data or a dataframe fragment. |
| Compile scope dependencies and execution | No | Carry scope references, static filters, action bindings, and required inputs through compilation and portable plans. Schedule scope actions before every invocation that relies on their result, include dependencies in cycle and invocation validation, and keep scope execution distinct from feature-producing actions. Fail preflight on missing scope actions or unavailable required capabilities before workflow data I/O. |
| Apply scope consistently during execution | No | Apply resolved scope selections to profile observations at a defined engine boundary so all data-producing fragments and downstream calculations obey the same included-row semantics. Preserve eager/lazy behavior through the adapter contract, handle empty selections and range boundaries deterministically, and fail explicitly when a scope cannot be applied to a representation. Do not interpret descriptive text as executable or silently widen/narrow a scope. |
| Test, document, and migrate executable scopes | No | Add unit, integration, and adapter conformance coverage for static and action-produced scopes, list and range filters, independent time dimensions, hierarchical resolutions, empty results, invalid columns and types, lazy execution, and custom-scope limitations. Update authoring, Python, CLI, engine, Explorer, examples, generated artifacts, and migration documentation to distinguish resolution from included-row scope. |
