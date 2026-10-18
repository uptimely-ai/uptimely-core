# Analytics Explorer

The Explorer turns an analytics definition into a visual, browsable website.
Use it to understand what an analytics project contains, how features relate,
and how the compiled plan connects its functions. It is generated from your
analytics JSON and saved execution plan, and is separate from running the analytics workflow.

## Build and preview

First build analytics JSON and the execution plan, then build the Explorer:

```sh
uptimely project build --project-root examples/pump_analytics
uptimely explorer build --project-root examples/pump_analytics
```

The build creates a complete website in
`examples/pump_analytics/_generated/explorer/`. Open its `index.html` in a
browser, or start a local preview server:

```sh
uptimely explorer serve --project-root examples/pump_analytics
```

Open <http://127.0.0.1:8001/>. Stop the server with **Ctrl+C**. `serve` builds
the Explorer before starting the server, so it is the quickest way to preview
your generated artifacts. The CLI loads the saved plan without recompiling it.
Use matching analytics and plan files from the same project build.

## What you’ll find

Use the sidebar to explore:

| Section | What it shows |
| --- | --- |
| **Analytics** | An overview of the model, its features, entities, datasets, dimensions, functions, and feature relationships. |
| **Plan** | The compiled functions, their dependencies, and the stages used to organize the plan. |
| **Execution / Data lineage** | A visual walkthrough of how declared inputs and outputs connect across functions. |

The feature graph focuses on relationships between analytics features. Plan
graphs focus on function dependencies. Graphs offer 2D and 3D views; use **Fit
graph** to bring the diagram into view and select a node to inspect it.

The data-lineage walkthrough is an illustration of the declared plan, not a
run of your functions. Its example table values and rows are placeholders; it
does not show real data or calculated results. Building the Explorer does not
execute the analytics workflow.

## Build options

`build` writes the static website without starting a server:

```sh
uptimely explorer build \
  --analytics _generated/analytics/analytics.json \
  --plan _generated/compile/execution_plan.json \
  --output _generated/explorer
```

| Option | Purpose |
| --- | --- |
| `--analytics` | Analytics JSON to display. Required unless `--project-root` is supplied. |
| `--plan` | Saved execution plan. Defaults to `_generated/compile/execution_plan.json` beneath the project root or current directory. |
| `--output` | Website output directory. Defaults to `_generated/explorer`. |
| `--project-root` | Project root for importing function entrypoints and resolving default paths. With this option, the default analytics file is `<project-root>/_generated/analytics/analytics.json`. |
| `--include-generated-at` | Include a build timestamp on analytics pages. |

`--analytics`, `--plan`, and `--output` paths are relative to the current working
directory. `--project-root` makes the project's functions importable and
provides default paths; it does not change the working directory.

## Preview options

`serve` builds the site and serves it for local review:

```sh
uptimely explorer serve \
  --project-root examples/pump_analytics \
  --port 8001
```

| Option | Purpose |
| --- | --- |
| `--analytics` | Analytics JSON to display. Defaults to `_generated/analytics/analytics.json` under `--project-root`, or under the current directory when no project root is set. |
| `--plan` | Saved execution plan. Defaults to `_generated/compile/execution_plan.json` beneath the project root or current directory. |
| `--directory` | Website output directory. Defaults to `_generated/explorer` under `--project-root`, or under the current directory otherwise. |
| `--project-root` | Project root for importing function entrypoints and resolving default paths. |
| `--host` | Address to serve on. Defaults to `127.0.0.1` (this machine only). |
| `--port` | Port to serve on. Defaults to `8001`; use `0` to choose an available port. |

The preview server builds once when it starts; it does not watch for file
changes. Run `project build` again and rerun `serve` to preview updates.
Alternatively, run `build` whenever you need to refresh the website files.

## Publish or share

The Explorer is a static website. To publish it, build the site and host the
entire output directory with a static web host; do not publish only
`index.html`, because the section pages and their navigation are alongside it.
The website can be moved or hosted under a URL path.

The preview server has no authentication or TLS and is intended only for local
review. Avoid binding it to `0.0.0.0` unless you intend to expose it to other
machines. For private analytics, use hosting that requires authentication.
Some styling and graph visualizations load from external services, so a network
connection is needed for the full visual experience.

For the command workflow used by the examples, see the
[examples guide](../../examples/README.md). For programmatic website generation,
see the [Explorer API reference](../reference/api/explorer.md).
