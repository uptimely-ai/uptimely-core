# Row context

`uptimely.spec.row_context` defines the runtime row-window values passed to analytical
functions. Python declarations for requesting those windows live in
[uptimely.spec.python.row_context](python.md#row_context).

<div class="api-reference" markdown="1">

## row_context

Import `RowContext`, `ContextExtent`, and `UNBOUNDED` from
`uptimely.spec.row_context`.
The Python authoring module provides binding helpers, not aliases of these
runtime types and constants.

Use a bare integer as row-count shorthand, and reference a declared direction
from the compute arguments when the function also needs that value:

```python
import uptimely as up
from uptimely.spec.row_context import RowContext

up.Operator(
    id="rolling_mean",
    interface=up.Interface(...),
    row_context=RowContext(before=1),
    compute=up.Binding(
        function=rolling_mean,
        arguments={"before": up.ref.row_context("before")},
    ),
)
```

`ref.row_context("before")` and `ref.row_context("after")` resolve to the
scalar extent: a row or step count, a duration string, or `"unbounded"`.
An empty direction resolves to `0`. `ref.row_context("dimension")` resolves
the declared dimension ID and raises an error if no dimension is declared.

::: uptimely.spec.row_context
    options:
      heading_level: 3
      show_root_heading: false
      members: [ContextExtent, RowContext, duration_nanoseconds, UNBOUNDED, CountExtent, TimeExtent]

</div>
