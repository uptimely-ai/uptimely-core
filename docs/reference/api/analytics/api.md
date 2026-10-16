# Analytics operations

`uptimely.analytics.api` provides the application-level operations for loading,
converting, and preparing analytics.

Loading and Python conversion perform semantic validation. Preparation resolves
functions and calls without adding derived state to the
[analytics document](model.md).

<div class="api-reference" markdown="1">

## api

::: uptimely.analytics.api
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - load_analytics
        - from_python
        - prepare_analytics

</div>
