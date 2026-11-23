# Dataframes and merge functions

## Dataframes and merge functions

`merge_by_grain` is the built-in Polars merge function. Provide a custom merge
function when the built-in behavior does not fit.
Compiled calls to the built-in merge include the target profile's declared
relation keys in `key_columns`, so lower-grain fragments join on shared keys
instead of becoming Cartesian products.

::: uptimely.library.merge.polars
    options:
      heading_level: 2
      show_root_heading: false
      members: [merge_by_grain]
