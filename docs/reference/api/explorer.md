# Analytics Explorer

`uptimely.explorer` generates documentation and visualizations of spec.
These outputs describe an analytics project, not this Python API reference.

<div class="api-reference" markdown="1">

## explorer

`uptimely.explorer.explorer` provides the website renderer.
`Explorer.create_html` generates the complete static website with spec, feature
graph, and execution plan pages. Individual HTML report exports are not
supported.

This is a low-level renderer: it does not create or validate the managed
`_generated/build/` bundle. Use `uptimely project build` for the project
workflow consumed by the Engine, Explorer server, feature-graph CLI, and MCP.

Pass an existing `ExecutionPlan` to `Explorer(spec_definition, plan=plan)` to
render that plan without recompilation. The plan is required. Use the optional
`features` argument to identify selected output features, or omit it for an
all-features plan. Spec pages always describe the complete model; plan and
execution pages describe only the supplied plan. Supply a plan built from the
same spec document; the Explorer does not verify their correspondence.

Spec-definition and portable-plan JSON exports remain available through
their respective spec and compiler APIs; the explorer writes HTML only.

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
