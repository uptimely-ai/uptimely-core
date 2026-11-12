# Analytics Explorer

The Explorer uses a versioned JSON presentation model and a packaged static
frontend. Build projects with `uptimely project build`, preview them with
`uptimely explore`, and export the frontend and snapshot with
`uptimely explorer export`. See the [Explorer page](../architecture/explorer.md)
for the workflow and [CLI reference](../cli/explorer.md) for command options.

<div class="api-reference" markdown="1">

## Presentation data

`uptimely.explorer.presentation` prepares and validates the data consumed by
the static Explorer. `build_presentation_data` accepts an explicit spec and
compiled execution plan; it does not compile plans, execute analytical
functions, or write files.

::: uptimely.explorer.presentation
    options:
      heading_level: 3
      show_root_heading: false
      members: [ExplorerPresentationData, build_presentation_data, validate_presentation_data]

## Presentation sections

The modules under `uptimely.explorer.sections` prepare catalog, plan, graph,
and animation data. They do not generate HTML or write output files.

::: uptimely.explorer.sections.feature_lineage
    options:
      heading_level: 3
      show_root_heading: false
      members: [feature_lineage_payload, build_context]

::: uptimely.explorer.sections.invocation_lineage
    options:
      heading_level: 3
      show_root_heading: false
      members: [invocation_lineage_payload, invocation_label, invocation_label_lines]

::: uptimely.explorer.sections.data_lineage
    options:
      heading_level: 3
      show_root_heading: false
      members: [DataLineageColumn, DataLineageStep, build_context]

## `graph_style`

`uptimely.explorer.graph_style` defines the shared visual style metadata for
lineage and topology graphs.

::: uptimely.explorer.graph_style
    options:
      heading_level: 3
      show_root_heading: false
      members: [GraphStyle]

For dependency analysis, see [feature graphs](feature-graph.md).

</div>
