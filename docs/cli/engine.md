# `uptimely run`

Execute the plan in the project's last successful active build:

```console
uptimely run \
  [PROJECT_ROOT] [--project-root PATH] [--src-path PATH] [--build] [--config CONFIG_OR_PATH] \
  [--validate] [--log-level LEVEL] [--preview [ROWS]]
```

Give the project directory positionally after `run`, or use
`--project-root PATH`. Do not use both. If omitted, the current working
directory is used.

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | — | Current working directory | Project root containing the active build and function entrypoints. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | — | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--src-path PATH` | `code.src` | Bundled project source<br>If absent, the configured value or `src` | Explicit Python source directory, relative to the project root or given as an absolute path. Overrides the default for this run. |
| `--build` | — | Disabled | Build and publish the project before execution, then run the newly published build. |
| `--config CONFIG_OR_PATH` | — | Root `uptimely.toml`<br>Otherwise built-in defaults | Pass a config name such as `prod` to load `config/prod.toml`, recursively overriding root `uptimely.toml`. Pass a TOML path to load that file alone without merging root settings. Relative paths resolve from the current working directory. |
| `--validate` | — | Disabled | Check invocation inputs and results against analytical contracts. |
| `--log-level LEVEL` | — | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes execution details. Replaces `--verbose`. |
| `--preview [ROWS]` | `engine.preview_rows` | No console preview by default<br>Bare `--preview` uses `engine.preview_rows` (default `5`) | Set the saved preview row limit and log those rows from each final profile after successful execution at info level. Without this option, saved previews use `engine.preview_rows`. |

Console display reuses the saved sample rather than executing the lazy query again.
Use `--log-level debug` to see the absolute Python source directory selected
for the run and whether it came from the bundle, an override, or a fallback.
See [Run artifacts](../artifacts/run.md#latest-run-artifacts) for preview collection,
query costs, and timing, and [Preview run results](../guides/preview.md) for
console output behavior.

See [Build a project](../guides/build.md), [Preview run results](../guides/preview.md),
and [Validate at runtime](../guides/runtime-validation.md) for related workflows, and
[Execution logging](../guides/logging.md#execution-logging) for log details.
