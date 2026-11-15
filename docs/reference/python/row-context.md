# Row context

`RowContext` describes which nearby rows a calculation needs. Use it when a
function depends on earlier, later, or all rows in a profile. Python helpers
for declaring these needs are listed in [Python authoring](python.md).

<div class="api-reference" markdown="1">

## row_context

Import `RowContext`, `ContextExtent`, and `UNBOUNDED` from
`uptimely.spec.row_context`.

Use a bare integer as row-count shorthand, and reference a declared direction
from the compute or stage arguments when the function also needs that value:

```python
import polars as pl
import uptimely as up
from uptimely.spec.row_context import RowContext


def rolling_mean(dataset: pl.DataFrame, value: str, output: str, before: int) -> pl.DataFrame:
    return dataset.with_columns(pl.col(value).rolling_mean(window_size=before + 1).alias(output))


up.Operator(
    id="rolling_mean",
    outputs=[up.Feature(id="mean")],
    row_context=RowContext(before=1),
    compute=up.Binding(
        rolling_mean,
        dataset=up.ref.dataset(),
        value=up.ref.feature("value"),
        output=up.ref.feature("mean").id,
        before=up.ref.row_context("before"),
    ),
)
```

`ref.row_context("before")` and `ref.row_context("after")` pass the requested
extent to the function. `ref.row_context("dimension")` passes the dimension ID.

::: uptimely.spec.row_context
    options:
      heading_level: 3
      show_root_heading: false
      members: [ContextExtent, RowContext, duration_nanoseconds, UNBOUNDED, CountExtent, TimeExtent]

</div>
