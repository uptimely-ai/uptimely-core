# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building and inspecting analytics, compiling execution plans, running
workflows, and generating the Analytics Explorer.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

<div class="api-reference" markdown="1">

## Command map

| Command | Reference | Purpose |
| --- | --- | --- |
| `uptimely analytics` | [Analytics](cli/analytics.md) | Build analytics JSON from Python declarations or inspect feature dependencies. |
| `uptimely engine` | [Engine](cli/engine.md) | Run an analytics workflow. |
| `uptimely examples` | [Examples](cli/examples.md) | Download runnable example projects. |
| `uptimely explorer` | [Explorer](cli/explorer.md) | Build or serve the Analytics Explorer website. |
| `uptimely plan` | [Plan](cli/plan.md) | Compile analytics into a portable execution plan. |

## Typical workflow

From an installed package, download examples and serve the pump analytics
Explorer:

```console
uptimely examples download
uptimely explorer serve --project-root examples/pump_analytics
```

To run a project, first export its Python declaration if needed, then compile
and execute:

```console
uptimely analytics build \
  --module examples.pump_analytics.config.analytics.analytics \
  --project-root . \
  --output examples/pump_analytics/_generated/analytics/analytics.json
uptimely plan build --project-root examples/pump_analytics
uptimely engine run --project-root examples/pump_analytics
```

The command defaults and options are documented on each command page. Paths
explicitly supplied on the command line are used as given; default generated
paths are resolved from `--project-root`, or from the current working
directory when no project root is specified. The `uptimely-mcp` server is a
separate optional command; see [AI agents](../components/ai.md).

</div>
