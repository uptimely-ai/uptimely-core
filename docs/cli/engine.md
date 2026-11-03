# `uptimely engine`

Use the top-level shortcut `uptimely run` to execute a workflow. It accepts the
same options as the grouped `uptimely engine run` command.

## `engine run`

Execute the plan in the project's last successful active build:

```console
uptimely run \
  [PROJECT_ROOT] [--project-root PATH] [--config PATH] \
  [--validate] [--log-level LEVEL] [--preview [ROWS]]
```

Give the project directory positionally after `run`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is `uptimely engine run [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build and function entrypoints. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--config PATH` | No | `config/config.json` under the project root or current working directory | Engine settings and required runtime control parameter values in JSON. |
| `--validate` | No | Disabled | Validate declared inputs and dataframe contracts at every execution step, including eager and lazy frames. Lazy value checks can repeatedly execute upstream queries. |
| `--log-level LEVEL` | No | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes execution details and validation traces. Replaces `--verbose`. |
| `--preview [ROWS]` | No | Disabled; 5 rows when supplied without a count | Log the first positive number of rows from each final profile after successful execution at info level. |

For example, preview five rows per profile, or request a specific row limit:

```console
uptimely run examples/pump_analytics
uptimely run --preview
uptimely run --preview 10
```

Previews show all columns and omit the Polars shape line. They are logged after
the completion summary and any debug details. Levels above `info` hide previews
and the completion summary. Lazy frames are limited before
collection, but their upstream operations may still require substantial work or
repeat computation. Execution timing excludes preview collection and display.
Previews can expose profile contents in logs; enable them only when appropriate.

Use `uptimely build` or the grouped `uptimely project build` command to change
the execution plan or feature scope. Engine executes the saved
build without compiling or generating artifacts. Saved-build integrity,
configuration, and backend compatibility are always checked; per-step runtime
validation is opt-in:

```console
uptimely run examples/pump_analytics --validate
uptimely run examples/pump_analytics --validate --log-level debug
```

The log level applies to Uptimely loggers, not third-party dependency loggers.
It does not enable validation; use `--validate` to run the runtime checks.
Debug headings use `Invocation: read_constants [read]`, with the function ID
below when different. Subsections are `Requirements:`, `Fragment:`,
`Main frame:`, and `Merge:`, shown only when reached.
The merge section shows the target profile, join kind, keys,
and cardinality; initial fragments are identified as initialization without a
join. Internal invocation IDs remain unchanged.

Without `--validate`, the engine still binds arguments and assembles declared
output fragments, but skips input-feature, schema/type, uniqueness, row-count,
coverage, and feature-collision checks. Native dataframe and function errors
can still fail execution. Skipped checks are not deferred to writes or final
collection. This runs the plan's
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
by `$params.<name>` must have an entry. Use these for framework controls such
as environment-specific read and write locations, not dataset contents or
analytical values:

```json
{
  "engine": {"backend": {}},
  "params": {
    "source_path": "data/input.parquet"
  }
}
```

See the [execution engine specification](../components/engine.md) for parameter
references and backend settings.
