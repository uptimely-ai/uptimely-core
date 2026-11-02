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
| **Overview** | Project and spec versions, catalog counts, plan counts, and build scope. |
| **Catalogs** | Entities, datasets, dimensions, and functions from the spec. |
| **Feature lineage** | Feature and action nodes with their declared relationships. |
| **Invocation lineage** | Compiled invocation nodes and dependency links. |
| **Plan** | Execution stages, invocation arguments, and dependency details. |
| **Animation** | An illustrative walkthrough of the declared execution stages and tables. |

The lineage views present selectable nodes and their metadata alongside the
declared dependencies. Animation values and rows are illustrative placeholders;
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

For command arguments and options, see the
[Explorer CLI reference](../cli/explorer.md). For the presentation-data API,
see the [Python reference](../python/explorer.md).
