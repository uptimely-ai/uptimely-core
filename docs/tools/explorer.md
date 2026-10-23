# Analytics Explorer

The Explorer turns a spec definition into a visual, browsable website.
Use it to understand what an analytics project contains, how features relate,
and how the compiled plan connects its functions. `project build` generates the
complete project bundle, including its website.

## Build and preview

Build the complete bundle:

```sh
uptimely project build --project-root examples/pump_analytics
```

`explorer serve` validates the active build and serves its saved website. It
does not load source, compile, render, or write artifacts:

```sh
uptimely explorer serve --project-root examples/pump_analytics
```

Open <http://127.0.0.1:8001/>. Stop the server with **Ctrl+C**. The CLI holds
a read lock on the active build until the server exits, preventing a rebuild
from replacing files while they are being served.

If the active build is missing, incomplete, or invalid, `serve` exits before
binding and prints a recovery `project build` command. A scoped build is labeled
on the website: spec pages describe the complete model, while plan and execution
pages describe the selected outputs and their dependencies.

## What you’ll find

Use the sidebar to explore:

| Section | What it shows |
| --- | --- |
| **Spec** | An overview of the model, its features, entities, datasets, dimensions, functions, and feature relationships. |
| **Plan** | The compiled functions, their dependencies, and the stages used to organize the plan. |
| **Execution / Data lineage** | A visual walkthrough of how declared inputs and outputs connect across functions. |

Every page shares a top bar with the project name and a home icon linking to the
project overview, plus a **Full build** or **Partial build** badge. Unnamed
projects show **Untitled analytics project**. Partial builds include
only selected outputs and their dependencies in plan and execution pages;
spec pages always show the complete model. Hover over the badge for coverage
details, also available to screen readers.

The feature graph focuses on relationships between spec features. Plan
graphs focus on function dependencies. Both use the same **2D / 3D** switch next
to the graph title,
**Zoom in**, **Zoom out**, **Fit graph**, collapsible legend, and selected-node
details panel. Click a node to highlight its upstream dependencies and downstream
dependents; the selection is preserved when switching dimensions. The feature
graph retains its entity colors and the execution graph retains its stage lanes
and operation colors when no node is selected.

The graph views have distinct navigation and heading icons: Feature graph uses
a teal network icon for feature relationships, while Execution graph uses an
orange workflow icon for left-to-right processing dependencies. These accents
identify the views; graph nodes retain their data-specific colors.

The data-lineage walkthrough is an illustration of the declared plan, not a
run of your functions. Its example table values and rows are placeholders; it
does not show real data or calculated results. Building the project bundle does
not execute the analytics workflow.

## Preview options

`serve` serves the website from the active project build:

```sh
uptimely explorer serve \
  --project-root examples/pump_analytics \
  --port 8001
```

| Option | Purpose |
| --- | --- |
| `--project-root` | Project root containing the active build. Defaults to the current working directory. |
| `--host` | Address to serve on. Defaults to `127.0.0.1` (this machine only). |
| `--port` | Port to serve on. Defaults to `8001`; use `0` to choose an available port. |

The preview server serves the saved files without watching for changes. Rebuild
the active project bundle with `uptimely project build`, then rerun `serve` to
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
[Explorer API reference](../reference/api/explorer.md).
