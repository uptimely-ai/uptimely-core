# Spec functions and arguments

## Functions

Each function declaration names an implementation, its return contract, and
the arguments it accepts. Operators reuse these declarations with different
bindings, feature dependencies, and target profiles. A descriptive category
groups functions but does not determine execution.

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
calculated results. Frame operations are derived from dataframe signatures for
Explorer presentation and are not stored in the Spec. See
[Function contracts](../intro/functions.md#functions-and-contracts) for the signature mapping,
and the [Compiler](../intro/compiler.md) page for validation details.

Python authoring infers `dataframe` or `none` from unambiguous annotations.
Otherwise, an explicit return contract is required.

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
