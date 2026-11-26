# Python functions and YAML specs

Specifications can be authored in YAML, while calculation functions remain
ordinary Python. YAML keeps project declarations separate from the code that
implements calculations.

For file layout, references, and a complete example, see
[YAML specification authoring](yaml-authoring.md) and the [example
project](../intro/example-project.md).

## Operators

An operator connects a function to a profile. Its `inputs` and `outputs`
declare feature dependencies and outputs, and its `args` mapping passes named
arguments to the function. If `inputs` is omitted, feature references in the
arguments are used to infer dependencies. Set `inputs: []` to disable that
inference.

Every operator requires a `function`. Add `merge` when its returned fragment
must be integrated into the target dataset.

### References

Use `$input.<feature>` and `$output.<feature>` to refer to input and output
features in arguments. Input references infer dependencies unless the feature
is an operator output. Explicit `inputs` override inference. Output references
also declare output features, including any needed descriptions, types, or
units under `features`.

Use `$paths.<name>` for a file or directory configured in the project's
`paths` map. Use `$params.<name>` for a scalar configured in `params`.
See [Runtime values](configuration.md#runtime-values) for runtime resolution
rules.

### When to use merge

See [Fragment and merge](../concepts/dataframes.md#fragments-and-datasets)
for when a merge is needed and how results are accumulated.

Declare the default merge in YAML when an operator's returned fragment must be
integrated into its target dataset:

```yaml
assembly:
  read_limits:
    function: project_io:read_limits
    outputs: [pressure_limit]
    args:
      source: "$paths.limits_source"
    merge: default
```

A custom merge mapping uses a `function` and `args` fields. Bind
`dataset` to `"$profiles.@.dataset"` and `fragment` to
`"$operators.@.fragment"`, and return the complete target. The function's
dataset argument must allow `None` for initialization.

### Seeds and execution order

`Profile.seed` must define the operator id returning the
initial complete dataset. Seed must not use merge, because the target dataset does not exist before it. Seed dataset can read data or transform a non-nullable foreign dataframe.

Seed dataset can contain only the dimension, but may contain feature columns additionally.

## Row context

Use a bare integer as row-count shorthand, and reference a declared direction
from the function arguments when the calculation also needs that value. In a
profile where `value` is available:

```yaml
assembly:
  rolling_mean:
    function: analytics:rolling_mean
    row_context:
      before:
        rows: 1
      after: {}
    args:
      value: "$input.value"
      output: "$output.mean"
      before: "$operators.@.row_context.before"
```
