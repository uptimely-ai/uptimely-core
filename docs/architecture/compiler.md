# Compiler

The Compiler transforms a Spec into a portable execution plan. It validates
the declarations, resolves the work required for the selected features, and
orders that work for the Engine. It does not execute analytical functions.

The [Project](project.md) component uses the Compiler during a build. The
resulting bundle contains both the Spec and plan, which the Engine consumes
later.

## Key concepts

### Operators and invocations

Spec operators declare how functions use inputs and produce outputs. The
Compiler turns this declared work into plan invocations, each representing a
function call. An operator can result in more than one invocation, for example
when a compute function produces a fragment that needs a separate merge.
Operators describe intent in the Spec; invocations are the executable steps in
the plan.

### Dependencies and stages

Declared feature inputs determine which invocations depend on others. The
Compiler resolves those dependencies, selects prerequisites for requested
features, and groups invocations into ordered stages. Dependencies must run
before their consumers; invocations in the same stage have no declared
dependency between them.

### Bound arguments

The plan records function arguments resolved from Spec declarations, including
references to features and profiles. References to runtime data are left for
the Engine to resolve during execution.

### Validation

Before creating the plan, the Compiler checks the Spec and the feasibility of
the requested feature selection. It also checks function entrypoints and, when
enabled, whether their signatures match the declared argument and return
contracts. These checks catch declaration problems before execution, but do
not verify that function implementations calculate correct results.

## Plan

The execution plan is the Compiler's portable description of what the Engine
will call, what each call needs, and how the calls depend on one another. It is
data, not executable Python, and does not contain function implementations.
The Engine uses it together with the Spec and runtime configuration.

The plan is stored as JSON in `execution_plan.json` inside the build bundle,
alongside `spec.json`. Project builds normally place these files in
`_generated/build/`.

### Structure

The versioned JSON object has four root fields:

```json
{
  "plan_version": 13,
  "required_backend": "polars",
  "invocations": [
    {
      "id": "read-pump-data--a1b2c3d4e5",
      "role": "compute",
      "result": "target",
      "function_id": "read_pump_data",
      "operator_id": "read",
      "profile_id": "pump_telemetry",
      "entrypoint": "pump_io:read_pump_data",
      "arguments": {},
      "input_features": [],
      "output_features": ["pressure"],
      "dependency_ids": []
    }
  ],
  "stages": [
    ["read-pump-data--a1b2c3d4e5"]
  ]
}
```

| Field | Meaning |
| --- | --- |
| `plan_version` | Version of the portable plan format. The current supported version is `13`. |
| `required_backend` | Dataframe backend required by the plan. The built-in compiler currently emits `polars`. |
| `invocations` | Ordered list of executable function calls and their contracts. |
| `stages` | Lists of invocation IDs grouped by execution order. |

### Invocations

The example shows the main shape; actual invocation objects also include
execution contracts and runtime metadata. Each invocation describes one
planned function call. Its portable fields are:

| Field | Purpose |
| --- | --- |
| `id` | Unique opaque identifier for this invocation. Consumers should not parse its spelling. |
| `role` | Binding role: `compute` for the main function call or `merge` for a separate fragment merge. |
| `result` | How the function result is handled: `none`, complete `target`, or staged `fragment`. |
| `operator_kind` | Descriptive operator label used by tools and diagnostics. Execution behavior is declared by the other contract fields. |
| `produces_features` | Whether this invocation publishes its outputs as feature dependencies. |
| `is_sink` | Whether this invocation performs a configured publication or write. |
| `dataframe_input_scope` | Declares the scope of dataframe input provided to the invocation. |
| `fragment_dimensions` | Describes the allowed dimensional grain of a fragment result relative to its target. |
| `row_count_relation` | States whether output rows must preserve the existing row count or may differ. |
| `key_relation` | States whether output keys must match existing keys or may differ. |
| `row_order_relation` | States whether output row order must be preserved or may differ. |
| `existing_data_relation` | States whether existing dataframe values must be preserved or may be changed. |
| `entrypoint` | Import location of the Python function the Engine calls. |
| `function_id` | ID of the Spec function declaration used by this invocation. |
| `operator_id` | ID of the Spec operator declaration that produces this invocation. |
| `profile_id` | ID of the profile whose dataframe is supplied or updated, or `null` when not applicable. |
| `arguments` | Function arguments resolved from the Spec. Runtime storage references remain for the Engine to resolve. |
| `dependency_ids` | IDs of invocations that must complete before this invocation. |
| `output_features` | Feature IDs declared as outputs of the associated operation. |
| `input_features` | Feature IDs declared as inputs to the associated operation. |
| `target_identifiers` | Ordered identifier columns that define target rows for the invocation's profile. |
| `fragment_keys` | Identifier and relation columns that may be used to align a fragment with its target. |
| `output_types` | Logical types for declared output columns, with `null` where a type is not declared. |
| `column_types` | Logical types for profile identifier and feature columns used by runtime validation. |
| `argument_types` | Declared types of the function's arguments. |
| `return_type` | Inspected Python return annotation, if available and signature validation is enabled. |
| `package` | Package distribution name and version associated with the entrypoint, when available. |
| `row_context` | Declared row-context requirement, or `null` when none is specified. |

### Stages

Every invocation appears exactly once in `stages`, and each dependency must be
in an earlier stage. Invocations within one stage have no declared dependency
on each other. The plan is checked for supported format, valid references, and
a schedule consistent with its dependencies when it is loaded.

### Versioning

`plan_version` identifies the serialized execution-plan format independently
of the Spec format. Increment it when an incompatible change is made to the
plan structure or its contract. A runtime accepts only the plan version it
supports and does not migrate older plans. After upgrading to a runtime that
requires a newer plan version, rebuild the bundle from the source Spec.

## Learn more

See the [Spec reference](spec.md) for declaration semantics and the
[Python Compiler API](../reference/python/compiler.md) for compilation and plan
serialization details.
