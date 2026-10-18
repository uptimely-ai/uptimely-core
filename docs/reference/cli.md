# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building project bundles, inspecting feature dependencies, running analytics
workflows, and previewing the Analytics Explorer.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

<div class="api-reference" markdown="1">

## Command map

| Command | Reference | Purpose |
| --- | --- | --- |
| `uptimely spec` | [Spec](cli/spec.md) | Inspect feature dependencies. |
| `uptimely engine` | [Engine](cli/engine.md) | Run an analytics workflow. |
| `uptimely examples` | [Examples](cli/examples.md) | Download runnable example projects. |
| `uptimely explorer` | [Explorer](cli/explorer.md) | Preview the Analytics Explorer website. |
| `uptimely project` | [Project](cli/project.md) | Build and publish a complete active bundle. |

## Typical workflow

From an installed package, download examples and build the complete active
bundle, including its spec, execution plan, and Explorer website:

```console
uptimely examples download
uptimely project build --project-root examples/pump_analytics
```

Run the saved execution plan from the active build:

```console
uptimely engine run --project-root examples/pump_analytics
```

The command defaults and options are documented on each command page. Project
build consumers use the active bundle under `_generated/build/`; rebuild it
with `uptimely project build` to change the saved plan or feature scope. The
`uptimely-mcp` server is a separate optional command; see [AI agents](../tools/ai.md).

</div>
