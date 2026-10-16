# `uptimely plan`

## `plan build`

Compile analytics into a portable execution-plan JSON document:

```console
uptimely plan build \
  [--analytics PATH] [--project-root PATH] [--features NAME ...] \
  [--verbose] [--output PATH]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--analytics PATH` | No | `_generated/analytics/analytics.json` under the project root or current working directory | Analytics JSON input. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print execution stages and function dependencies when enabled. |
| `--output PATH` | No | `_generated/compile/execution_plan.json` under the project root or current working directory | Plan JSON destination. |

Example:

```console
uptimely plan build --project-root examples/pump_analytics --verbose
```
