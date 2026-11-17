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
| `--src-path PATH` | `application.src_path` | TOML setting if set<br>Otherwise the literal directory name `src` | Python source directory, relative to the project root or given as an absolute path. Overrides the configured value for this command. |
| `--build` | — | Disabled | Build and publish the project before execution, then run the newly published build. |
| `--config CONFIG_OR_PATH` | — | Root `uptimely.toml`<br>Otherwise built-in defaults | Pass a config name such as `prod` to load `config/prod.toml`, recursively overriding root `uptimely.toml`. Pass a TOML path to load that file alone without merging root settings. Relative paths resolve from the current working directory. |
| `--validate` | — | Disabled | Validate declared inputs and dataframe contracts at every execution step, including eager and lazy frames. Lazy value checks can repeatedly execute upstream queries. |
| `--log-level LEVEL` | — | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes execution details and validation traces. Replaces `--verbose`. |
| `--preview [ROWS]` | `engine.preview_rows` | No console preview by default<br>Bare `--preview` uses `engine.preview_rows` (default `5`) | Set the saved preview row limit and log those rows from each final profile after successful execution at info level. Without this option, saved previews use `engine.preview_rows`. |

Console display reuses the saved sample rather than executing the lazy query again.
See [Run artifacts](../artifacts/run.md#latest-run-artifacts) for preview collection,
query costs, and timing, and [Preview logging](../guides/logging.md#preview-logging)
for console output behavior.

See [Execution options](../guides/build-and-run.md#execution-options)
for preview, validation, and build-before-run examples, and
[Execution logging](../guides/logging.md#execution-logging) for log details.
