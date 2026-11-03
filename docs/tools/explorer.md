# Analytics Explorer

The Explorer is a static JavaScript frontend for browsing a project's
specification, compiled plan, and illustrative execution data. The project
build publishes a versioned JSON snapshot; the frontend never imports or runs
the project's analytical functions.

## Build and preview

Build the project before previewing it:

```sh
uptimely project build examples/pump_analytics
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/>. Stop the server with **Ctrl+C**. The server
serves the packaged frontend and reads the current snapshot from
`_generated/explorer.json` on each API request. It does not watch for source
changes. Rebuild the project and refresh the browser to view an updated
snapshot; an already-running server can pick up the replacement snapshot.

Use `uptimely explore --build` to build once before serving. A missing or
invalid snapshot is reported with a project-build recovery command. Scoped
builds include the full spec catalog and a plan limited to selected outputs
and their dependencies.

## Browse the project

The Explorer contains:

| Section | What it shows |
| --- | --- |
| **Project home** | Project identity, counts, build scope, and the spec-to-execution journey. |
| **Spec** | Overview, separate profile/feature/dimension/function catalogs, dimension resolution hierarchies, and feature lineage. |
| **Plan** | Overview, invocation topology, and execution stages with argument bindings. |
| **Execution** | Profile-specific animation of declared processing steps and illustrative tables. |

The original desktop navigation and contextual sidebars can be collapsed
independently. On narrow screens, the hamburger button opens project navigation.
A persistent bar below the header provides access to the page's context menu;
tap it to open a centered dialog with item navigation, legends, and details.
On graph pages, **Legend & details** opens the legend and selected-node information;
the graph controls remain separate below it.
Close the dialog with its **Close** button, the backdrop, or **Escape**.
Graph view and zoom controls, and animation profile and playback controls,
remain accessible in the bar without opening the dialog.
Catalogs start with an overview; select an item in the contextual
sidebar to inspect its details. Item selections support browser back/forward
navigation and direct links. Menu links switch views client-side without
reloading the document or refetching the snapshot. Refresh the browser after
rebuilding to load updated project data. Graphs and animation playback are
stopped when leaving their view.

Lineage and topology offer interactive **2D** and **3D** views, zoom, reset,
profile legends, and selectable node details. For animation, choose a profile
before using **Previous**, **Play**, and **Next**.
Animation values and rows are illustrative placeholders;
they are not execution results. Running the project's workflow is a separate
operation using `uptimely run`.

## Export for static hosting

Export the packaged HTML, CSS, JavaScript, and current snapshot to a directory
or ZIP archive:

```sh
uptimely explorer export examples/pump_analytics --output docs/examples/pump_analytics
uptimely explorer export examples/pump_analytics --output pump-analytics-explorer.zip
```

The export uses a relative URL for its JSON data, so it can be hosted beneath a
documentation site's path prefix. Build the project again before exporting
after source changes. The same ZIP is available from the preview server at
`/api/explorer/export`.

As in the pre-migration UI, styling, fonts, icons, syntax highlighting, and
graph libraries load from public CDNs. Both preview and exported pages need
network access to those services. Project snapshot data is fetched only from
the configured preview API or exported relative JSON file.

For command arguments and options, see the
[Explorer CLI reference](../cli/explorer.md). For the presentation-data API,
see the [Python reference](../python/explorer.md).
