# Dataframes and merge functions

## Dataframes and merge functions

`Dataset`, `Fragment`, and `Merge` are dataframe helpers. The Engine's plan
runner does not use them to prepare or dispatch calls.
`merge_by_grain` is the built-in Polars merge function. Provide a custom merge
function when the built-in behavior does not fit.
Compiled calls to the built-in merge include the target profile's declared
relation keys in `key_columns`, so lower-grain fragments join on shared keys
instead of becoming Cartesian products.

::: uptimely.engine.dataframe.dataset
    options:
      heading_level: 2
      show_root_heading: false
      members: [Dataset]

::: uptimely.engine.dataframe.fragment
    options:
      heading_level: 2
      show_root_heading: false
      members: [Fragment]

::: uptimely.engine.dataframe.merge
    options:
      heading_level: 2
      show_root_heading: false
      members: [Merge]

::: uptimely.library.merge.polars
    options:
      heading_level: 2
      show_root_heading: false
      members: [merge_by_grain]
