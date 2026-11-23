# Execution plan

The execution plan is the versioned `plan.json` build artifact. It records
function calls, their semantic metadata, and their execution order. It does not
contain function implementations.

The call schedule is stored in `plan.json` alongside `spec.json` in the build
bundle. Project builds normally place these files in `artifacts/build/`.

## Structure

The versioned JSON object groups calls by execution stage:

```json
{
  "plan_version": 16,
  "required_backend": "polars",
  "invocations": [
    {
      "id": "read-pump-data--a1b2c3d4e5",
      "entrypoint": "pump_io:read_pump_data",
      "arguments": {},
      "returns": "pump",
      "semantics": {
        "role": "compute",
        "result": "target",
        "produces_features": true,
        "is_sink": false,
        "is_workflow": false,
        "is_seed": true,
        "dataframe_input_scope": "unrestricted",
        "fragment_dimensions": "not_applicable",
        "row_count_relation": "unrestricted",
        "key_relation": "unrestricted",
        "row_order_relation": "unrestricted",
        "existing_data_relation": "unrestricted",
        "function_id": "read_pump_data",
        "operator_id": "read_pump_data",
        "profile_id": "pump",
        "dependency_ids": [],
        "output_features": [],
        "input_features": [],
        "row_context": null,
        "target_identifiers": ["pump_id"],
        "fragment_keys": [],
        "output_types": {},
        "column_types": {"pump_id": "string"},
        "argument_types": {},
        "return_type": "pandas.DataFrame",
        "package": {
          "distribution": "pump-package",
          "version": "1.0.0"
        }
      }
    }
  ],
  "stages": [["read-pump-data--a1b2c3d4e5"]]
}
```

`plan.json` contains the plan version, required backend, function calls,
return bindings, and their semantic metadata. Each invocation keeps call data
(`id`, `entrypoint`, `arguments`, and `returns`) separate from `semantics`.
The `stages` field orders
invocations by dependency level.

The executable call data consists of:

- `id`, a stable invocation identifier used in the schedule and dependency graph.
- `entrypoint`, the function implementation that the invocation calls.
- `arguments`, the resolved argument values or runtime references passed to that
  entrypoint.
- `returns`, the target profile whose accumulated dataframe is returned by the
  invocation, or `null` when it returns no profile result.

The plan requires a convention for passing an invocation's return value to the
arguments of later invocations that depend on it. `returns` identifies the
profile whose accumulated dataframe is available as the return binding.
It is `null` for invocations that do not publish an accumulated profile
dataframe. Uptimely's built-in Engine resolves this state in memory.
Another Engine or orchestrator can persist dataframe results and supply them to
downstream tasks as task outputs or artifact references. Temporary fragment
returns used only by merge invocations remain execution details rather than
accumulated profile returns.

## Stages

Every invocation appears exactly once in `stages`. Invocations within one
stage have no declared dependency on each other. When a bundle is loaded, the
schedule is checked against the dependencies in each invocation's semantics.

## Semantics

The `semantics` object is analytical metadata for an invocation. It describes
the invocation's role and result, traces it to a Spec operator and profile,
declares data dependencies and contracts, and supports runtime validation.
The fields are part of each invocation in `plan.json`, not a separate artifact.

An Engine should theoretically be able to execute a plan without interpreting
the `semantics` object. Invocation attributes provide the executable function
call: `id`, `entrypoint`, and resolved `arguments`. A generic runner also needs
the execution order and a convention for passing each invocation's return value
to later invocations' arguments. It does not need to catalog analytical roles or
inspect the meaning of those calls.

The built-in Engine also uses `semantics` for analytical dispatch and optional
contract validation. This includes identifying target transforms, fragments,
merges, sinks, and dataframe inputs. Those behaviors are separate from basic
function invocation. A portable plan format could therefore move such routing
information into explicit call data and leave `semantics` for optional
provenance and validation.

| Field | Meaning |
| --- | --- |
| `role` | Invocation role. `compute` calculates or produces a value. `merge` publishes a computed fragment to its target profile. |
| `result` | Result routing for a compute invocation: `none` for no dataframe result, `target` for a target-profile dataframe, or `fragment` for a temporary dataframe consumed by one merge invocation. Merge invocations always use `target`. |
| `produces_features` | Whether the invocation produces declared logical features. |
| `is_sink` | Whether the invocation is an output or side-effect sink. |
| `is_workflow` | Whether the invocation is a workflow function without ordinary dataframe output. Workflow invocations must be compute invocations, sinks, and non-dataframe calls. |
| `is_seed` | Whether the invocation is the seed operator for its profile. |
| `dataframe_input_scope` | Dataframe input interpretation: `none`, `target`, `foreign`, or `unrestricted`. It tells the Engine whether a dataframe argument refers to no profile, the target profile, a foreign profile, or is context-dependent. |
| `fragment_dimensions` | Fragment behavior for result validation: `target`, `subset`, or `not_applicable`. It is required for fragment invocations. |
| `row_count_relation` | Declared row-count relationship to existing target data: `same` or `unrestricted`. |
| `key_relation` | Declared identifier relationship: `identical` or `unrestricted`. |
| `row_order_relation` | Declared row-order relationship: `preserve` or `unrestricted`. |
| `existing_data_relation` | Declared relationship to existing target data: `preserve` or `unrestricted`. |
| `function_id` | Stable identifier of the function declaration used by the invocation. |
| `operator_id` | Stable identifier of the source operator declaration. |
| `profile_id` | Stable identifier of the target or source profile, or `null` when no profile applies. |
| `dependency_ids` | Invocation IDs that must finish before this invocation. These IDs define the schedule dependencies in addition to the stage list. |
| `output_features` | Logical feature IDs declared as outputs. A target identifier is not included in this list. |
| `input_features` | Logical feature IDs declared as inputs. |
| `row_context` | Observation window required around each row. It can declare a dimension and bounded or unbounded observations before and after the current row. It is `null` when no row context applies. |
| `target_identifiers` | Identifier columns of the target profile. |
| `fragment_keys` | Identifier and key columns used when assembling a fragment with the target profile. |
| `output_types` | Logical output feature IDs mapped to their declared data types. A feature with no declared type has a `null` value. |
| `column_types` | Available target and key column names mapped to declared data types. |
| `argument_types` | Invocation argument names mapped to their declared function argument types. |
| `return_type` | Declared Python return annotation, or `null` when no annotation is available. |
| `package` | Installed package provenance for the entrypoint, containing `distribution` and `version`, or `null` when provenance is unavailable. |

The fields `dependency_ids` and `stages` both constrain scheduling:
`dependency_ids` records the graph, while `stages` is the resolved execution
order. An invocation can be called only after every invocation named in
`dependency_ids` has succeeded.

## Versioning

`plan_version` identifies the format of `plan.json`, independently of the Spec
format. Increment it when an incompatible change is made to the plan structure
or contract. A runtime accepts only the plan version it supports and does not
migrate older plans. After upgrading to a runtime that requires a newer plan
version, rebuild the bundle from the source Spec.

## Learn more

See the [Compiler](../concepts/compiler.md) for how the plan is produced, the
[Engine](../concepts/engine.md) for how it is executed, and the
[Python Compiler API](../python/compiler.md) for plan serialization.
