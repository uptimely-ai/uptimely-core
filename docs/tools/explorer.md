# Analytics Explorer

The Explorer turns a spec definition into a visual, browsable website.
Use it to understand what an analytics project contains, how features relate,
and how the compiled plan connects its invocations. `build` generates the
complete project bundle, including its website.

## Build and preview

Build the complete bundle:

```sh
uptimely build examples/pump_analytics
```

`explore` validates the active build and serves its saved website. It
does not load source, compile, render, or write artifacts:

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/>. Stop the server with **Ctrl+C**. The CLI holds
a read lock on the active build until the server exits, preventing a rebuild
from replacing files while they are being served.

If the active build is missing, incomplete, or invalid, `explore` exits before
binding and prints a recovery `build` command. A scoped build is labeled
on the website: spec pages describe the complete model, while plan and execution
pages describe the selected outputs and their dependencies.

## What you’ll find

Use the sidebar on larger screens, or open the hamburger menu on mobile, to
explore:

| Section | What it shows |
| --- | --- |
| **Spec** | An overview of the model, its features, entities, datasets, dimensions, functions, and feature relationships. The functions page opens with a bar chart of the catalog by function kind that links to each kind's group, and every group heading pairs its function count with a miniature infographic of the transformation. Function cards show how many actions use the function, a plain-language summary, and syntax-highlighted Python examples, and detail arguments with their types, return, and raise documentation parsed from implementation docstrings when signature validation is enabled. |
| **Plan** | The compiled invocations, their dependencies, and the stages used to organize the plan. |
| **Execution / Animation** | A visual walkthrough of how data is assembled after each action. |

On desktop, the sidebar reaches the top of the page and sizes to its contents.
Its header shows the project name and a home link to the project overview. A
**Full build** or **Partial build** badge spans the content width at the bottom,
below the independently scrolling navigation links.
Full-build coverage uses muted styling. Use the toggle beside the project title
to collapse the sidebar to icons; the same button restores the labels.
On mobile, only the top bar is shown
until the hamburger menu is opened; build badges are never shown.
Unnamed projects show **Untitled analytics project**. Partial builds include
only selected outputs and their dependencies in plan and execution pages;
spec pages always show the complete model. Hover over the badge for coverage
details, also available to screen readers.

Features, datasets, dimensions, entities, functions, and plan stages have a context panel
beside the main navigation. Select an entry to show only that item; a selected
stage shows all its invocations. Each panel starts with **Overview**, selected
by default, showing summary statistics and category charts rather than item
details. These summarize features by dataset, datasets by entity, entities by dimension count,
dimensions by type, functions by kind, and invocations by stage and function kind.
Individual items remain separate, spacious views without outer card containers;
the selected item's title replaces the section heading at the top. Returning to
Overview restores the section title. Tables and code examples retain their own formatting.
Dataset details appear directly beneath the schema, with labeled filtering,
coverage, logical ordering, and action information when declared; no expansion
is required.
URL fragments preserve selections when
sharing links or using browser Back and
Forward. Selecting an entry opens the view at the top, rather than scrolling
past its heading to the item's anchor. Datasets are grouped by entity; functions are grouped by kind, with
kind links selecting the first function in that group. Without JavaScript, all
items remain readable and the links jump to their content. The panel scrolls independently
and can collapse to an icon rail. On mobile, use **Browse datasets** (or the
corresponding page label) to open the panel, then select an entry, press
**Escape**, or use **Close** to dismiss it.
The context menu matches the main navigation's flat background, typography,
spacing, and section-colored icons. Group labels and muted counts organize its
entries, with Overview above a separator. Selection does not add a highlight.
Feature entries are grouped by dataset. Each feature view shows its description,
type, unit, owning entity and dataset, and producing action and function.

Lineage visualizes feature inputs and outputs. Topology
visualizes dependencies between compiled invocations. Both use the same
**2D / 3D** switch next to the graph title,
**Zoom in**, **Zoom out**, **Reset graph**, collapsible legend, and selected-node
details panel. On these two pages, the legend and selected-item details live in a
full-height context panel immediately to the right of the desktop navigation,
leaving the graph unobstructed. The panel header aligns with the main navigation
header and contains the view's icon and title, with the dimension,
zoom, and reset controls below. Its own collapse toggle reduces it to an icon
rail independently of the main navigation. On mobile, **Lineage controls** opens a drawer
over the graph; use **Close** or **Escape** to dismiss it.
Click a node to highlight its upstream dependencies and downstream
dependents; the selection is preserved when switching dimensions. The
2D Lineage view groups features and actions into horizontal dataset lanes.
Dependencies flow left to right across the whole graph, including between datasets;
actions stay in their owning dataset's lane. Connected datasets are placed next
to one another where possible, and long edges use lane gutters to avoid cards.
Dataset names appear in the legend and selected-node details, not on swimlane
rows. Feature cards retain their dataset colors and action cards retain their
function color. Features without a dataset share an
unassigned lane. Selecting a node highlights its dependencies across lanes.
The 2D Topology view uses the same dataset lanes and edge routing,
with execution stages ordered left to right and invocation cards colored by
dataset, matching feature colors and the dataset legend. Labeled stage headers,
subtle column shading, and vertical separators
form a grid with the dataset rows. Invocations from different datasets in the
same stage share a column. Graph fitting includes the dataset rows and stage headers.
Hover over an invocation or select it to inspect its dataset and stage.
In 3D, the Topology graph uses the same dataset-colored spheres,
node sizes, label spacing, and edge length settings as Lineage.
**Reset graph** clears the selection and dependency highlights in both dimensions
and fits the current view to show the whole graph.

Lineage and Topology views have distinct navigation and heading icons:
Lineage uses a teal network icon for feature relationships, while
Topology uses an orange workflow icon for dependencies between plan
invocations. These accents identify the views; graph nodes retain their
data-specific colors.

The Animation walkthrough is an illustration of the declared plan, not a
run of your functions. Its example table values and rows are placeholders; it
does not show real data or calculated results. Building the project bundle does
not execute the analytics workflow.

## Preview options

`explore` serves the website from the active project build:

```sh
uptimely explore \
  examples/pump_analytics \
  --port 8001
```

| Option | Purpose |
| --- | --- |
| `PROJECT_ROOT` | Project root containing the active build. Defaults to the current working directory; `--project-root PATH` is an explicit alternative. |
| `--host` | Address to serve on. Defaults to `127.0.0.1` (this machine only). |
| `--port` | Port to serve on. Defaults to `8001`; use `0` to choose an available port. |

The preview server serves the saved files without watching for changes. Rebuild
the active project bundle with `uptimely build`, then rerun `explore` to
preview source updates.

## Publish or share

The Explorer is a static website. To publish it, build the site and host the
entire output directory with a static web host; do not publish only
`index.html`, because the section pages and their navigation are alongside it.
The generated `js/` and `css/` directories contain the Explorer's scripts and
styles and must be included too. The website can be moved or hosted under a URL path.

The preview server has no authentication or TLS and is intended only for local
review. Avoid binding it to `0.0.0.0` unless you intend to expose it to other
machines. For private spec, use hosting that requires authentication.
Some styling and graph visualizations load from external services, so a network
connection is needed for the full visual experience.

For the command workflow used by the examples, see the
[examples guide](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/README.md).
For programmatic website generation, see the
[Explorer API reference](../python/explorer.md).
