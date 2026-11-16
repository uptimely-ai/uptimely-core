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

At info level, the CLI announces the start of the engine run. With `--build`,
it also announces the project-bundle build before building it. Successful runs
log individual processed-profile details first, followed by
`Engine processed X profiles in Y s.` The engine scope is not logged.
After a successful run and any requested previews, an info log shows the
`uptimely explore --project-root PATH` command for opening that project's Explorer.

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

For example, preview the configured number of rows per profile, or request a
specific row limit:

```console
uptimely run example
uptimely run --preview
uptimely run --preview 10
```

Previews show all columns and omit the Polars shape line. They are logged after
the completion summary and processed-profile summary, before any debug details.
Levels above `info` hide previews, the completion summary, and processed-profile
details. Lazy frames are limited before
collection, but their upstream operations may still require substantial work or
repeat computation. Execution timing excludes preview collection, artifact
publication, and display. Console display reuses the saved sample rather than
executing the lazy query again.

Use `uptimely build` to change the execution plan or feature scope. By default,
Engine executes the saved build without compiling or rebuilding it.
`--build` rebuilds from the project's discovered spec source before execution.
The CLI always checks saved-build integrity, configuration, and backend
compatibility. Per-step runtime validation is opt-in:

```console
uptimely run example --validate
uptimely run example --validate --log-level debug
uptimely run example --build
```

If the project uses a non-default source directory, pass the same `--src-path`
to both the build and each run that imports its local modules.

The log level applies to Uptimely loggers, not third-party dependency loggers.
It does not enable validation. Use `--validate` to run the runtime checks.
Execution debug logs use flat messages with the logger's module name,
rather than headers, indentation, or bullets. For example:

```text
DEBUG    | Check fragment dataframe type
DEBUG    | Merging into profile pump_profile
```

Module prefixes identify where each message originates. Invocation start messages
identify the operator, function, binding role, and result handling.
Structured logs use the invocation IDs from the saved plan. Newly compiled
plans use [compact invocation IDs](../formats/execution-plan.md#invocations).
Rebuild the project to adopt them.
