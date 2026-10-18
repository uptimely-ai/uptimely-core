# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building and inspecting specifications, compiling execution plans, running
analytics workflows, and generating the Analytics Explorer.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

<div class="api-reference" markdown="1">

## Command map

| Command | Reference | Purpose |
| --- | --- | --- |
| `uptimely spec` | [Spec](cli/spec.md) | Build spec JSON from Python or JSON sources, or inspect feature dependencies. |
| `uptimely engine` | [Engine](cli/engine.md) | Run an analytics workflow. |
| `uptimely examples` | [Examples](cli/examples.md) | Download runnable example projects. |
| `uptimely explorer` | [Explorer](cli/explorer.md) | Build or serve the Analytics Explorer website. |
| `uptimely plan` | [Plan](cli/plan.md) | Compile spec into a portable execution plan. |
| `uptimely project` | [Project](cli/project.md) | Build spec and compile the saved execution plan together. |

## Typical workflow

From an installed package, download examples and serve the pump analytics
Analytics Explorer:

```console
uptimely examples download
uptimely project build --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

Build prepares spec and plan artifacts without executing the workflow.
To execute the saved plan:

```console
uptimely engine run --project-root examples/pump_analytics --compile false
```

You can still build and execute using individual commands:

```console
uptimely spec build --project-root examples/pump_analytics
uptimely plan build --project-root examples/pump_analytics
uptimely engine run --project-root examples/pump_analytics
```

The command defaults and options are documented on each command page. Paths
explicitly supplied on the command line are used as given; default generated
paths are resolved from `--project-root`, or from the current working
directory when no project root is specified. The `uptimely-mcp` server is a
separate optional command; see [AI agents](../tools/ai.md).

</div>
