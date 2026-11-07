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
Frontend assets are revalidated on reload so browsers pick up updated styles and
scripts together. After upgrading from a version that allowed browser caching,
perform a hard refresh once to clear previously cached assets.

Use `uptimely explore --build` to build once before serving. A missing or
invalid snapshot is reported with a project-build recovery command. Scoped
builds include the full spec catalog and a plan limited to selected outputs
and their dependencies.

## Browse the project

The Explorer contains:

| Section | What it shows |
| --- | --- |
| **Project home** | Project identity, counts, build scope, and the spec-to-execution journey. |
| **Analytical model** | Profile/feature/dimension/function catalogs, profile cards sized by operator count, feature counts by role in the Features overview, dimension resolution hierarchies, and feature lineage. |
| **Execution plan** | Overview, invocation topology, and execution stages with argument bindings. |
| **Run results** | Profile-specific animation, latest-run information, run logs, and saved previews for each profile. |

The main menu groups equally aligned links under non-clickable section labels,
with subtle separators and a highlighted current page. Desktop navigation has a
stable width and collapses to an icon rail; the contextual sidebar collapses
independently. On narrow screens, the hamburger button opens project navigation.
A persistent bar below the header provides access to the page's context menu;
tap it to open a centered dialog with item navigation, legends, and details.
On graph pages, **Legend & details** opens the legend and selected-node information;
the graph controls remain separate below it.
Close the dialog with its **Close** button, the backdrop, or **Escape**.
Graph view and zoom controls, and animation profile and playback controls,
remain accessible in the bar without opening the dialog.
Catalog overview pages summarize their content; Profiles uses one compact card
per profile, with operator count indicating profile size and grain shown as
dimension/resolution paths. Other overviews share count cards and
distribution charts. Schema, argument bindings, and saved previews share table
styling, with badges for roles and run status.
Navigation and data-type icons identify content; section headings and count
cards avoid repeating those icons.
Navigation and content icons use neutral colors matching their labels. A single
cyan accent marks selection and interactive emphasis. Status badges, data-role
badges, graph legends, and log syntax retain semantic colors; labels and shapes
also convey their meaning without relying on color alone.
Catalogs start with an Overview; select an item in the contextual
sidebar to inspect its details. Item selections support browser back/forward
navigation and direct links. Menu links switch views client-side without
reloading the document or refetching the snapshot. Refresh the browser after
rebuilding to load updated project data. Graphs and animation playback are
stopped when leaving their view.

Dimension details label the selected dimension above its title. The Resolution
levels section uses compact cards connected by tree branches. Each card shows
the resolution ID and its data key with a data-type icon (or type text when no
icon is available).

Profile details show a Produced schema table with one row per declared column, listing
its role, data type, unit, and producing operator from top to bottom. Features
without a declared producer show "None declared"; multiple producers are listed.
The Operator section lists every declared operator, including vectorized
transformations, with its function, argument bindings, and input/output features.

Feature details group labeled role, data type, unit, and profile values beneath
the feature name. The producing operator card uses
the same layout as profile details, including its function, resolved arguments,
and all declared input and output features.
The Used by section at the bottom lists linked badges for features produced by
operators in the same profile that directly consume the selected feature.
Both views connect the input and output columns with a small operator icon and
directional arrows, stacking the flow vertically on narrow screens.

The Preview context menu groups datasets by profile category when categories are
available. Profiles without a category appear under Uncategorized; without any
categories, the menu remains a flat list.

Lineage and topology offer interactive **2D** and **3D** views, zoom, reset,
profile legends, and selectable node details. **Graph legend** is a collapsed visual key:
expand it for profile-color chips and node or function-kind icons. It explains
the graph rather than filtering it; profile colors do not indicate run status.
The operator key follows the operator visibility toggle. Selected-node details
show the node name and icon above labeled sections for its definition, profile,
and data flow. Invocation details also separate argument bindings and connection
scope, link to the owning operator, and distinguish flow notes from metadata.
Flow notes explain what the selected step does, clarify that dataset-ready
markers describe the plan rather than a completed run, and explain highlighted arrows.
Long identifiers and argument values wrap without being truncated.
Every graph-control button has
a tooltip identifying its action. The reset icon sits alongside zoom in and
zoom out in the viewport button group. It clears selection
and fits the current graph.
Invocation topology in 2D uses one swimlane per profile, with stages progressing
left to right. A thick, muted **Dataset** spine shows the dataset accumulation
surface: compute branches sit above it, merges publish fragments onto it, vectorize
enriches it directly, and effects sit below it. Cards show a single function
label; owning operator identifiers remain available in tooltips and selected-node
details so compute and merge calls can be associated while separately selectable.
Profile names appear outside the stage grid on the left, aligned with their
Dataset spine, with the text to the left of the outlined table icon. The icon
and tapered connector mark where the accumulation journey begins, not an already
initialized dataframe. A filled badge containing the table icon and label
outside the grid on the right marks **Dataset ready**; scoped builds show
**Selected outputs ready**. Effect-only lanes show **No dataset produced**.
These markers describe the compiled plan, not runtime completion, and are not
invocations or dependency arrows. Writes remain separate consumers of the Dataset.
Dependent invocations progress left to right through stages. Independent
same-stage publishers form compact vertical groups in softly filled,
profile-colored rounded boxes; groups containing vectorize invocations have no
border and match the spine's color and opacity. The spine enters and exits each box at its edges,
rather than crossing behind its publishers, without implying an
execution order or adding dependency arrows. Groups have no text labels.
Cards use the same function-kind icons as the catalogs
instead of kind prefixes or publication descriptions.
Merge and vectorize borders use their profile's mainframe color; off-spine
computes and effects use neutral gray. The same role-based colors apply in 3D.
Icons and text stay neutral, and selection and dependency highlights retain
their accents.
The default merge is labeled **Merge by grain**, with a sparkle badge identifying
the automatically supplied binding. Its tooltip and details explain the badge;
custom merges use their operation names (humanizing underscore-separated names)
and have no automatic badge.
Both feature-lineage and Topology arrows share obstacle-aware routing and
bounded arrowhead sizing. They use short orthogonal paths with rounded corners and attach to
the appropriate card edge. Unobstructed neighbors connect directly; longer
dependencies route around intervening cards rather than detouring solely because
a stage is wide.
Topology selection highlights all upstream and downstream dependencies by default.
The route-icon highlight-scope button switches between **Full lineage** and
**Direct connections** (immediate inputs and consumers only). It is disabled
until an invocation is selected; its descriptive tooltip and details state the
current scope.
The toggle preserves the selection and applies to both 2D and 3D views. Direct
dependencies use stronger strokes and color than transitive lineage, which stays
visible all the way to upstream sources and downstream consumers.
Overview arrows are quiet, with prominent direction markers and animated particles
reserved for highlighted relationships. Unrelated arrows dim further on selection.
Highlighted paths are drawn above dimmed arrows so overlapping dependencies
cannot hide the selected lineage.
Feature lineage retains its existing full-lineage highlighting.
Hovering an invocation shows its declared contribution: **Adds** for vectorize,
**Publishes** for merge, and **Declared outputs** for other kinds. These labels
do not claim to describe the complete intermediate Dataset.
The guide is schematic, not an
additional dependency or a claim about publication order; only arrows represent
compiled dependencies. Node details show declared outputs and merge keys, not
inferred dataset sizes or schemas. The context legend lists only profiles;
selecting an invocation reveals compact notes on its Dataset role, plan markers,
grouping, and direct versus full-lineage highlighting. The owning-operator link
shows its humanized name and opens the operator declaration.
In 3D, labels also include function-kind icons;
merges use diamonds and vectorize uses cubes. That view remains a dependency
graph rather than an accumulation layout.
Feature lineage also offers
the function-icon **Show operators** toggle, enabled and highlighted by default.
Turn it off to connect input and output
features directly across each operator; shared dependencies appear as one edge.
All feature nodes remain visible, including isolated features. Operators without
inputs or outputs disappear without creating additional dependencies.
Feature labels in 2D and 3D show a data-type icon before the name. Selected-item
details show the declared type, including for transformer outputs; features
without a declared type use a generic icon.
The browser derives these views from the same snapshot, without rebuilding or
requesting additional data, including in static exports.
The selection is saved in the URL as `operators=show` or `operators=hide` and
supports refresh and browser back/forward. Switching detail preserves a selected
feature; hiding a selected operator clears selection. Each visited detail and
2D/3D combination retains its own viewport.
For animation, choose a profile
before using **Previous**, **Play**, and **Next**.
Animation values and rows are illustrative placeholders;
they are not execution results. Running the project's workflow is a separate
operation using `uptimely run`.

## Saved-run API

The server can read the latest execution artifacts independently of the build
presentation snapshot:

| Endpoint | Response |
| --- | --- |
| `GET /api/run` | Latest run manifest, including its build fingerprint, invocation outcomes, and profile preview index. |
| `GET /api/run/preview/{profile_id}` | One profile's saved preview, including its schema and sample rows or explicit preview error. |
| `GET /api/run/logs?offset=0&limit=100` | A page of structured log events; maximum page size is 1,000. |

Pass `?run_id=<manifest.run_id>` to preview and log requests to detect
replacement since the manifest was read. A replaced run returns
HTTP 409; reload the manifest before retrying. Missing runs or unknown profiles
return 404, and invalid or unreadable artifacts return 503. Responses are not
cached. No API request executes analytics.

Run storage does not use locking. Read after execution finishes; simultaneous
runs and reads during publication are not coordinated, and artifacts can be
briefly unavailable while the directory is replaced.

Runs overwrite `_generated/run/` completely; there is no history or run
format-version field. Their build fingerprint describes the loaded build at
execution time, so consumers must not assume a run belongs to a subsequently
rebuilt project. The **Info** page shows the latest run manifest, the **Log**
page shows its structured events in an editor-style, syntax-highlighted view,
and the **Preview** page displays one saved
profile sample at a time, titled with the selected profile's name, with a
context menu when there are multiple profiles.
Static export continues to include only the build presentation snapshot, not
run previews or logs, so these pages require the live Explorer API.

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
