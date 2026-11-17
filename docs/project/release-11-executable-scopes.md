# Release 11: Reusable profile filters and action-driven row scopes

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Reusable scope declarations

Turn profile scope from descriptive text into reusable, executable row
selection while keeping resolution (row detail) distinct from scope (included
rows).

**Prerequisites:** Specification model migration, Dataframe adapter API and
registry, and Arrow conversion and assembly.

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
| Reference reusable scopes from profiles | Yes | Replace descriptive profile scope text with references to named scopes. Keep resolution (row detail) distinct from scope (included rows). |
| Define scope declaration forms | Yes | Give each scope a name and exactly one of static `filters` or an `action`. |
| Define supported filter forms | Yes | Define list and range filters, empty selections, null handling, type compatibility, bound inclusivity, and how multiple filters combine. |
| Define filter columns and profile semantics | Yes | Specify whether filters target dimensions, features, or other dataset columns and how they apply at a profile's grain and resolution. |

## Work package: Static scope validation and documentation

Validate static filters against profile schemas and explain the authoring
contract.

**Prerequisites:** Reusable scope declarations.

| title | breaking | description |
|---|---|---|
| Validate filter references and values | No | Check scope references, structure, columns, value types, range bounds, and operators against profile schemas and grain. |
| Normalize static filters | No | Convert valid filters into a deterministic internal representation. Reject unsupported and inapplicable filters instead of ignoring them. |
| Report static filter diagnostics | No | Identify the scope, profile, column, and source path in validation errors. |
| Test and document static scopes | No | Cover list/range filters, independent time dimensions, hierarchical resolutions, empty results, and invalid columns or types. Document profile authoring and migration. |

## Work package: Action-driven scope contracts

Allow reusable project logic to compute the same row filters supported by
static scopes.

**Prerequisites:** Reusable scope declarations, Static scope validation and
documentation.

| title | breaking | description |
|---|---|---|
| Bind actions to reusable scopes | No | Bind a scope action to reusable project logic with declared arguments and dependencies. |
| Define action execution contracts | No | Define execution phase, purity and I/O expectations, and the exact return contract for scope actions. |
| Reuse static filter results | No | Require action results to use the static filter representation. Diagnose custom selections that cannot be represented by lists or ranges. |
| Validate action bindings and results | No | Validate action bindings and returned selections. Do not treat scope results as feature data or dataframe fragments. |
| Test action-driven scopes | No | Cover valid and invalid bindings, return values, dependencies, and unsupported custom selection forms. |

## Work package: Compile scope dependencies

Carry scope declarations into the plan and schedule actions before dependent
invocations.

**Prerequisites:** Action-driven scope contracts.

| title | breaking | description |
|---|---|---|
| Add scope data to portable plans | No | Carry scope references, static filters, action bindings, and required inputs through compilation and plan serialization. |
| Schedule scope actions before consumers | No | Run each required scope action before invocations that use its result. Keep scope actions distinct from feature-producing actions. |
| Validate scope dependency graphs | No | Include scope dependencies in cycle and invocation validation. |
| Preflight required scope capabilities | No | Fail before workflow data I/O when scope actions or required capabilities are unavailable. |

## Work package: Apply scopes during execution

Apply one resolved row-selection policy to all profile data and downstream
calculations.

**Prerequisites:** Compile scope dependencies and Arrow conversion and assembly.

| title | breaking | description |
|---|---|---|
| Apply resolved filters at the engine boundary | No | Apply selections to profile observations so all data-producing fragments and downstream calculations use the same included rows. |
| Preserve adapter and boundary semantics | No | Preserve eager/lazy behavior, handle empty selections and range boundaries deterministically, and fail when a scope cannot be applied to a representation. |
| Verify row-scope consistency | No | Test static and action-produced scopes, empty results, adapter behavior, and hierarchical resolutions. Never treat descriptive text as executable or silently widen/narrow a scope. |
| Update scope interfaces and migration guidance | No | Update Python, CLI, engine, Explorer, examples, generated artifacts, and migration docs to distinguish resolution from included-row scope. |
