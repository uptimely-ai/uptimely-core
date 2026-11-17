# Dataframes and merge functions

## Dataframes and merge functions

`Dataset` stores a profile's accumulated dataframe. `Fragment` represents the
data returned by a calculation. `Merge` combines a fragment with the dataset.
`merge_by_grain` is the built-in Polars merge function; provide a custom merge
function when the built-in behavior does not fit.

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
