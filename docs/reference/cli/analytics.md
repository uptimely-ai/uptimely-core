# `uptimely analytics`

Export a Python analytics declaration to the JSON analytics format, or inspect
feature dependencies in an analytics document.

## `analytics export`

```console
uptimely analytics export --module functions.analytics [--project-root PATH] [--output PATH]
```

The importable module must expose a `python_analytics` value of type
`PythonAnalytics`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--module` | Yes | None | Import path of the module exposing `python_analytics`. |
| `--project-root PATH` | No | Current working directory | Add this directory to Python's import path and use it as the base for the default output path. |
| `--output PATH` | No | `_generated/analytics/analytics.json` under `--project-root` or the current working directory | Destination JSON path. |

Example:

```console
uptimely analytics export \
  --module examples.pump_analytics.config.analytics.analytics \
  --project-root . \
  --output examples/pump_analytics/_generated/analytics/analytics.json
```

## `analytics feature-graph`

```console
uptimely analytics feature-graph [--analytics PATH] [--project-root PATH] [--features NAME ...] [--verbose]
```

Prints the number of features in the graph. When selected features are given,
also prints the size of their dependency subset. `--verbose` prints the graph
and selected subset as trees.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--analytics PATH` | No | `_generated/analytics/analytics.json` under the project root or current working directory | Analytics JSON input. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print graph details when enabled. |
