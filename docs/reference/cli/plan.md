# `uptimely plan`

## `plan build`

Compile spec into a portable execution-plan JSON document:

```console
uptimely plan build \
  [--spec PATH] [--project-root PATH] [--features NAME ...] \
  [--verbose] [--output PATH]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--spec PATH` | No | `_generated/spec/spec.json` under the project root or current working directory | Spec JSON input. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print execution stages and function dependencies when enabled. |
| `--output PATH` | No | `_generated/compile/execution_plan.json` under the project root or current working directory | Plan JSON destination. |

Example:

```console
uptimely plan build --project-root examples/pump_analytics --verbose
```
