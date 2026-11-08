# `uptimely engine`

Use the top-level shortcut `uptimely run` to execute a workflow. It accepts the
same options as the grouped `uptimely engine run` command.

## `engine run`

Execute the plan in the project's last successful active build:

```console
uptimely run \
  [PROJECT_ROOT] [--project-root PATH] [--build] [--config PATH] \
  [--validate] [--log-level LEVEL] [--preview [ROWS]]
```

Give the project directory positionally after `run`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is `uptimely engine run [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build and function entrypoints. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--build` | No | Disabled | Build and publish the project before execution, then run the newly published build. |
| `--config PATH` | No | `config/config.json` under the project root or current working directory | Engine settings and required runtime control parameter values in JSON. |
| `--validate` | No | Disabled | Validate declared inputs and dataframe contracts at every execution step, including eager and lazy frames. Lazy value checks can repeatedly execute upstream queries. |
| `--log-level LEVEL` | No | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes execution details and validation traces. Replaces `--verbose`. |
| `--preview [ROWS]` | No | Console display disabled; 5 rows when supplied without a count | Set the saved preview row limit and log those rows from each final profile after successful execution at info level. Without this option, five rows per profile are still saved. |

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
repeat computation. Execution timing excludes preview collection, artifact
publication, and display. Console display reuses the saved sample rather than
executing the lazy query again.

Use `uptimely build` or the grouped `uptimely project build` command to change
the execution plan or feature scope. By default, Engine executes the saved
build without compiling or rebuilding it. Add `--build` to rebuild from the
project's discovered spec source before execution. Saved-build integrity,
configuration, and backend compatibility are always checked; per-step runtime
validation is opt-in:

```console
uptimely run examples/pump_analytics --validate
uptimely run examples/pump_analytics --validate --log-level debug
uptimely run examples/pump_analytics --build
```

The log level applies to Uptimely loggers, not third-party dependency loggers.
It does not enable validation; use `--validate` to run the runtime checks.
Debug headings use `Invocation: read_constants [read]`, with the function ID
below when different. Subsections are `Requirements:`, `Fragment:`,
`Dataset:`, and `Merge:`, shown only when reached.
The merge section identifies the target profile and merge invocation.
Internal invocation IDs remain unchanged.

## Latest-run artifacts

Every execution saves `_generated/run/run.json`, `log.jsonl`, and
`preview/<profile>.json`. This replaces the previous run completely, including
previews for profiles that no longer appear. There is no run history or run
format-version field.

The manifest records UTC timestamps, execution duration, overall status, build
fingerprint and scope, engine settings, runtime-validation mode, per-invocation
statuses/timings/errors, and profile statistics and preview paths. Failed
invocations still produce a saved run with any available partial profile
results. Invalid configuration or build errors before execution do not
replace the previous run.

Previews are collected automatically, including for lazy frames, even without
`--preview`. Lazy queries are limited before collection, but this may still
perform expensive upstream work. Exact full-profile row counts are recorded
only for eager frames; lazy counts are `null`. Preview failures are recorded
separately and do not change the execution status. When console previews are
requested, an unavailable preview is also reported as a CLI error.

Logs use UTF-8 JSON Lines: one event per line with timestamp, severity, logger,
message, optional invocation/profile IDs, and exception details. Capture follows
configured logging levels and includes Python logs from the execution thread;
it does not redirect stdout/stderr or capture other threads' logs.

Saved samples and logs may contain sensitive project data. Parameter values
and environment variables are not copied into the manifest, but functions can
still include them in logs or outputs. Keep credentials out of engine settings
and log messages. Use `data/output/` for intentionally retained analytical data;
the generated run is a disposable diagnostic snapshot.

## Runtime validation and configuration

Without `--validate`, the engine still binds arguments, stages fragments, and
calls their scheduled merge functions. It skips input-feature, declared type,
key uniqueness, row-count, and coverage checks. Merge results must still be
dataframes with the complete expected target schema, and overlapping feature
columns are rejected. Native dataframe and function errors can also fail
execution. Skipped checks are not deferred to writes or final collection. This runs the plan's
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
