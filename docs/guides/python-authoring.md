# Python authoring

Maintaining a large json specification file manually can be challenging.

While json format remains as the source of truth, it is easier to manage the specification through Python interface.

## Why Python authoring

Python makes syntax easier to read and enable splitting specification to multiple modules, that can import each other.

You can create large number of almost similar profiles, features and operators with minimal number of code. Python "frontend" immediately tells you if you are referring to non-existing variables.

Also, python makes it easy to load and publish specification in any remote storage.

## How to do it?

For minimal working example, see the home page from Getting Started.

For larger example of Python authoring, see the example project in Getting Started.

## Operators

An `Operator` connects a function to a profile. Its `inputs` and `outputs`
declare feature dependencies and outputs, and its `Bind` takes a function
followed by its named arguments. If `inputs` is omitted, feature references in
the arguments are used to infer dependencies. Set `inputs=[]` to disable that
inference.

Every operator requires `compute=Bind(...)`. Add `merge` when its returned
fragment must be integrated into the target dataset.

### References

Use `ref` to refer to profile data, features, and other Spec values without
loading data during authoring. Both `ref.input("name")` and
`ref.input("name").id` pass the feature identifier and infer an input
dependency unless the feature is an operator output. Explicit `inputs` override
inference. Bind arguments must use `ref.input()` or `ref.output()` for feature
references. Declare `Feature` instances in `Operator.outputs`, not as argument
values.

Use `ref.paths("name")` for a file or directory configured in the project's
`paths` map. Use `ref.params("name")` for a scalar configured in `params`.
See [Runtime values](configuration.md#runtime-values) for runtime resolution
rules.

### When to use merge

See [Fragment and merge](../concepts/dataframes.md#fragments-and-datasets)
for when a merge is needed and how results are accumulated.

Use the default merge explicitly:

```python
Operator(
    outputs=[Feature(id="pressure_limit")],
    compute=Bind(
        ref.function("project_io:read_limits", returns="dataframe"),
        source=ref.paths("limits_source"),
    ),
    merge=merge.default(),
)
```

A custom `merge=Bind(...)` uses
`dataset=ref.dataset()` and `fragment=ref.fragment()` and returns the
complete target. Its dataset argument must allow `None` for initialization.

### Seeds and execution order

`Profile.seed` must define the operator id returning the
initial complete dataset. Seed must not use merge, because the target dataset does not exist before it. Seed dataset can read data or transform a non-nullable foreign dataframe.

Seed dataset can contain only the dimension, but may contain feature columns additionally.

## Row context

Use a bare integer as row-count shorthand, and reference a declared direction
from the operator's binding arguments when the function also needs that value:

```python
# script

import polars as pl
import uptimely as up
from uptimely.spec.row_context import RowContext


def rolling_mean(dataset: pl.DataFrame, value: str, output: str, before: int) -> pl.DataFrame:
    return dataset.with_columns(pl.col(value).rolling_mean(window_size=before + 1).alias(output))


up.Operator(
    id="rolling_mean",
    row_context=RowContext(before=1),
    compute=up.Bind(
        rolling_mean,
        dataset=up.ref.dataset(),
        value=up.ref.input("value"),
        output=up.ref.output("mean").id,
        before=up.ref.row_context("before"),
    ),
)
```
