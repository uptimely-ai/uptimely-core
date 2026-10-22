# `uptimely engine`

## `engine run`

Execute the plan in the project's last successful active build:

```console
uptimely engine run \
  [--project-root PATH] [--config PATH] [--verbose] [--preview [ROWS]]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Project root containing the active build and function entrypoints. |
| `--config PATH` | No | `config/engine.json` under the project root or current working directory | Engine settings and runtime bindings in JSON. |
| `--verbose` | No | `false` | Add saved-resource statistics, execution counts, calculated features, stages, and dataset registry details. |
| `--preview [ROWS]` | No | Disabled; 5 rows when supplied without a count | Log the first positive number of rows from each final dataset after successful execution, independently of `--verbose`. |

For example, preview five rows per dataset, or request a specific row limit:

```console
uptimely engine run --preview
uptimely engine run --preview 10
```

Previews show all columns and omit the Polars shape line. They are logged after
the completion summary and any verbose details. Lazy frames are limited before
collection, but their upstream operations may still require substantial work or
repeat computation. Execution timing excludes preview collection and display.
Previews can expose dataset contents in logs; enable them only when appropriate.

Build or rebuild the project with `uptimely project build` to change its
execution plan or feature scope. Engine validates and executes the saved build
without compiling or generating artifacts. This runs the plan's configured
functions, including write sinks, and may have external side effects. Missing
or invalid builds report a recovery command.

The engine configuration is validated as `EngineConfig`. It contains a
`backend` object for backend settings and a `bind` object for runtime values:

```json
{
  "backend": {},
  "bind": {}
}
```

See the [execution engine specification](../../components/engine.md) for
backend settings and runtime overrides.
