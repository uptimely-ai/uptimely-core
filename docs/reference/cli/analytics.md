# `uptimely analytics`

Build analytics JSON from Python declarations or JSON sources, or inspect
feature dependencies in an analytics document.

## `analytics build`

```console
uptimely analytics build [--module MODULE | --analytics PATH] [--project-root PATH] [--output PATH]
```

Without an explicit source, the command discovers
`config/analytics/analytics.py` or `config/analytics/analytics.json` beneath the
project root (the current directory by default). If both exist, select one
explicitly with `--module` or `--analytics`; neither takes precedence.

A Python module must expose a `python_analytics` value of type
`PythonAnalytics`. Discovered Python sources are imported with their package
context, preserving relative imports. Enclosing regular packages (directories
with `__init__.py`) are included in the module name. JSON sources are loaded
and validated before writing the generated document. Building does not execute
the analytics workflow, but importing Python declarations executes module-level code.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--module` | No | Discover the standard source | Import path of the module exposing `python_analytics`. Mutually exclusive with `--analytics`. |
| `--analytics PATH` | No | Discover the standard source | Source analytics JSON path. Mutually exclusive with `--module`. |
| `--project-root PATH` | No | Current working directory | Add this directory to Python's import path and use it as the base for the default output path. |
| `--output PATH` | No | `_generated/analytics/analytics.json` under `--project-root` or the current working directory | Destination JSON path. |

Example:

```console
uptimely analytics build --project-root examples/pump_analytics
```

Explicit Python source and output:

```console
uptimely analytics build \
  --module examples.pump_analytics.config.analytics.analytics \
  --project-root . \
  --output examples/pump_analytics/_generated/analytics/analytics.json
```

Explicit `--analytics` and `--output` paths are relative to the current working
directory, not `--project-root`. The command does not change working directories.

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
