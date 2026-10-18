# Analytics Explorer

The Explorer turns a spec definition into a visual, browsable website.
Use it to understand what an analytics project contains, how features relate,
and how the compiled plan connects its functions. During the active-build
migration, the Explorer CLI still consumes standalone spec and plan artifacts;
`project build` creates the new complete bundle, which the consumers will adopt
in a later step.

## Build and preview

For the current standalone Explorer commands, export the spec and compile the
plan before building or serving the website:

```sh
uptimely spec build --project-root examples/pump_analytics
uptimely plan build --project-root examples/pump_analytics
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
Use matching spec and plan files generated from the same source revision.

If `_generated` is empty or either input is missing, `build` and `serve` exit
without starting a server or generating inputs. Create the standalone inputs
with `uptimely spec build --project-root ...` and
`uptimely plan build --project-root ...`, then retry Explorer. For custom
inputs, check `--spec` and `--plan`. The new `project build` bundle is not yet
read by these consumer commands.

## What you’ll find

Use the sidebar to explore:

| Section | What it shows |
| --- | --- |
| **Spec** | An overview of the model, its features, entities, datasets, dimensions, functions, and feature relationships. |
| **Plan** | The compiled functions, their dependencies, and the stages used to organize the plan. |
| **Execution / Data lineage** | A visual walkthrough of how declared inputs and outputs connect across functions. |

The feature graph focuses on relationships between spec features. Plan
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
  --spec _generated/spec/spec.json \
  --plan _generated/compile/execution_plan.json \
  --output _generated/explorer
```

| Option | Purpose |
| --- | --- |
| `--spec` | Spec JSON to display. Required unless `--project-root` is supplied. |
| `--plan` | Saved execution plan. Defaults to `_generated/compile/execution_plan.json` beneath the project root or current directory. |
| `--output` | Website output directory. Defaults to `_generated/explorer`. |
| `--project-root` | Project root for importing function entrypoints and resolving default paths. With this option, the default spec file is `<project-root>/_generated/spec/spec.json`. |
| `--include-generated-at` | Include a build timestamp on spec pages. |

`--spec`, `--plan`, and `--output` paths are relative to the current working
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
| `--spec` | Spec JSON to display. Defaults to `_generated/spec/spec.json` under `--project-root`, or under the current directory when no project root is set. |
| `--plan` | Saved execution plan. Defaults to `_generated/compile/execution_plan.json` beneath the project root or current directory. |
| `--directory` | Website output directory. Defaults to `_generated/explorer` under `--project-root`, or under the current directory otherwise. |
| `--project-root` | Project root for importing function entrypoints and resolving default paths. |
| `--host` | Address to serve on. Defaults to `127.0.0.1` (this machine only). |
| `--port` | Port to serve on. Defaults to `8001`; use `0` to choose an available port. |

The preview server builds once when it starts; it does not watch for file
changes. Re-export the spec and plan, then rerun `serve` to preview updates.
Alternatively, run `build` whenever you need to refresh the website files.

## Publish or share

The Explorer is a static website. To publish it, build the site and host the
entire output directory with a static web host; do not publish only
`index.html`, because the section pages and their navigation are alongside it.
The website can be moved or hosted under a URL path.

The preview server has no authentication or TLS and is intended only for local
review. Avoid binding it to `0.0.0.0` unless you intend to expose it to other
machines. For private spec, use hosting that requires authentication.
Some styling and graph visualizations load from external services, so a network
connection is needed for the full visual experience.

For the command workflow used by the examples, see the
[examples guide](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/README.md).
For programmatic website generation, see the
[Explorer API reference](../reference/api/explorer.md).
