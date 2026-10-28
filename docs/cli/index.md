# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building project bundles, inspecting feature dependencies, running analytics
workflows, and previewing the Analytics Explorer.

For common tasks, use the top-level shortcuts `uptimely build`, `uptimely run`,
and `uptimely explore`. The grouped forms `uptimely project build`,
`uptimely engine run`, and `uptimely explorer serve` remain available and accept
the same options. Project-specific commands accept an optional project
directory immediately after the action name, such as
`uptimely build examples/pump_analytics`. If omitted, the current working
directory is used. `--project-root PATH` is also supported as an explicit
alternative; do not pass both forms.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

<div class="api-reference" markdown="1">

## Command map

| Command | Reference | Purpose |
| --- | --- | --- |
| `uptimely spec feature-graph` | [Spec feature-graph](spec.md) | Inspect feature dependencies. |
| `uptimely engine` | [Engine](engine.md) | Run an analytics workflow. |
| `uptimely examples` | [Examples](examples.md) | Download runnable example projects. |
| `uptimely explorer` | [Explorer](explorer.md) | Preview the Analytics Explorer website. |
| `uptimely project` | [Project](project.md) | Build and publish a complete active bundle. |
| `uptimely build` | [Project build](project.md) | Shortcut for `uptimely project build`. |
| `uptimely run` | [Engine run](engine.md) | Shortcut for `uptimely engine run`. |
| `uptimely explore` | [Explorer serve](explorer.md) | Shortcut for `uptimely explorer serve`. |

## Typical workflow

From an installed package, download examples and build the complete active
bundle, including its spec, execution plan, and Explorer website:

```console
uptimely examples
uptimely build examples/pump_analytics
```

Run the saved execution plan from the active build:

```console
uptimely run examples/pump_analytics
```

The command defaults and options are documented on each command page. Project
build consumers use the active bundle under `_generated/build/`; rebuild it
with `uptimely build` (or `uptimely project build`) to change the saved plan or
feature scope. The `uptimely-mcp` server is a separate optional command; see
[AI agents](../tools/ai.md).

</div>
