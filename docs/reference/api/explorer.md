# Analytics Explorer

`uptimely.explorer` generates documentation and visualizations of analytics.
These outputs describe an analytics project, not this Python API reference.

<div class="api-reference" markdown="1">

## explorer

`uptimely.explorer.explorer` provides the website export.
`Explorer.create_html` and the module-level `create_html` helper generate the
complete static website with analytics, feature graph, and execution plan pages.
Individual HTML report exports are not supported.

Pass an existing `ExecutionPlan` to `Explorer(analytics_definition, plan=plan)`
or `create_html(analytics_definition, output_path, plan=plan)` to render that plan
without recompilation. If omitted, the Python API compiles analytics as before.
Supply analytics and plan artifacts built from the same project revision; the
Explorer does not verify their correspondence. Function metadata inspection
may still import Python entrypoints, but analytics functions are not executed.

Analytics-definition and portable-plan JSON exports remain available through
their respective analytics and compiler APIs; the explorer writes HTML only.

::: uptimely.explorer.explorer
    options:
      heading_level: 3
      show_root_heading: false
      members: [Explorer, create_html]

## graph_render

`uptimely.explorer.graph_render` defines the visual style of rendered graphs.
For dependency analysis, see [feature graphs](feature-graph.md).

::: uptimely.explorer.graph_render
    options:
      heading_level: 3
      show_root_heading: false
      members: [GraphStyle]

</div>
