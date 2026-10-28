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
The renderer reuses its Jinja environment and compiled templates between pages
and website builds. Project-specific data is passed separately to each render.

Section implementations are modules under `uptimely.explorer.sections`:
`spec`, `plan`, `feature_graph`, `plan_graph`, and `data_lineage`. Each module
prepares its own display data. Page-producing sections use the concrete
`WebsiteSection` renderer in `uptimely.explorer.render`, with `WebsitePage`
definitions for templates, destinations, and navigation identifiers.
`WebsiteContext` supplies project identity and build scope without mixing them
into section-specific data. `Explorer` creates one shared `WebsiteContext` and
passes each section's `build_context` result to `SECTION.write_pages`; section
modules do not write files themselves. The plan-graph module only builds
payloads; its page is written through the plan section's page definition.

::: uptimely.explorer.explorer
    options:
      heading_level: 3
      show_root_heading: false
      members: [Explorer, create_html]

## graph_style

`uptimely.explorer.graph_style` defines the visual style shared by feature and
execution-plan graph sections. Graph payload preparation belongs to
`uptimely.explorer.sections.feature_graph` and
`uptimely.explorer.sections.plan_graph`. For dependency analysis, see
[feature graphs](feature-graph.md).

::: uptimely.explorer.graph_style
    options:
      heading_level: 3
      show_root_heading: false
      members: [GraphStyle]

</div>
