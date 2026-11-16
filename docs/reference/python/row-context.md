# Row-context utilities

`RowContext` describes which nearby rows a calculation needs. Use it when a
function depends on earlier, later, or all rows in a profile. Python helpers
for declaring these needs are listed in [Python authoring](../../guides/python/authoring.md#row-context).

<div class="api-reference" markdown="1">

## row_context

Import `RowContext`, `ContextExtent`, and `UNBOUNDED` from
`uptimely.spec.row_context`.

`ref.row_context("before")` and `ref.row_context("after")` pass the requested
extent to the function. `ref.row_context("dimension")` passes the dimension ID.

::: uptimely.spec.row_context
    options:
      heading_level: 3
      show_root_heading: false
      members: [ContextExtent, RowContext, duration_nanoseconds, UNBOUNDED, CountExtent, TimeExtent]

</div>
