# Analytics Explorer

`uptimely.explorer` generates documentation and visualizations of analytics.
These outputs describe an analytics project, not this Python API reference.

<div class="api-reference" markdown="1">

## explorer

`uptimely.explorer.explorer` provides the website and reference-data exports.
`Explorer.create_html` and the module-level `create_html` helper generate the
complete static website with analytics, feature graph, and execution plan pages.
Individual HTML report exports are not supported.

`Explorer.create_json` exports reference data; analytics and portable-plan JSON
exports remain available.

::: uptimely.explorer.explorer
    options:
      heading_level: 3
      show_root_heading: false
      members: [Explorer, create_html, create_json]

## graph_render

`uptimely.explorer.graph_render` defines the visual style of rendered graphs.
For dependency analysis, see [feature graphs](feature-graph.md).

::: uptimely.explorer.graph_render
    options:
      heading_level: 3
      show_root_heading: false
      members: [GraphStyle]

</div>
