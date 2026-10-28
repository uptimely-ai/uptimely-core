# `uptimely engine`

Use the top-level shortcut `uptimely run` to execute a workflow. It accepts the
same options as the grouped `uptimely engine run` command.

## `engine run`

Execute the plan in the project's last successful active build:

```console
uptimely run \
  [PROJECT_ROOT] [--project-root PATH] [--config PATH] \
  [--verbose] [--preview [ROWS]]
```

Give the project directory positionally after `run`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is `uptimely engine run [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build and function entrypoints. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--config PATH` | No | `config/config.json` under the project root or current working directory | Engine backend settings and required global scalar parameter values in JSON. |
| `--verbose` | No | `false` | Add saved-resource statistics, execution counts, calculated features, stages, and dataset registry details. |
| `--preview [ROWS]` | No | Disabled; 5 rows when supplied without a count | Log the first positive number of rows from each final dataset after successful execution, independently of `--verbose`. |

For example, preview five rows per dataset, or request a specific row limit:

```console
uptimely run examples/pump_analytics
uptimely run --preview
uptimely run --preview 10
```

Previews show all columns and omit the Polars shape line. They are logged after
the completion summary and any verbose details. Lazy frames are limited before
collection, but their upstream operations may still require substantial work or
repeat computation. Execution timing excludes preview collection and display.
Previews can expose dataset contents in logs; enable them only when appropriate.

Use `uptimely build` or the grouped `uptimely project build` command to change
the execution plan or feature scope. Engine validates and executes the saved
build without compiling or generating artifacts. This runs the plan's
configured functions, including write sinks, and may have external side
effects. Missing or invalid builds report a recovery command.

The `engine` section is validated as `EngineConfig` and contains backend
settings:

```json
{
  "backend": {}
}
```

Global scalar values are stored in the `params` object. A parameter referenced
by `$params.<name>` must have an entry:

```json
{
  "engine": {"backend": {}},
  "params": {
    "threshold": 10,
    "source_path": "data/input.parquet"
  }
}
```

See the [execution engine specification](../components/engine.md) for parameter
references and backend settings.
