# `uptimely explorer`

Preview the saved Analytics Explorer website locally. Use
[`uptimely project build`](project.md) to generate or replace the active
project bundle before serving it.

The shortcut `uptimely explore` serves the same saved website with the same
options as `uptimely explorer serve`.

## `explorer serve`

`serve` validates and serves the website from the active build. It does not
load source files, compile, render, or modify build artifacts. The active-build
read lock remains held while the server is running, so a rebuild cannot replace
the website until the server exits.

```console
uptimely explore \
  [PROJECT_ROOT] [--project-root PATH] [--host ADDRESS] [--port PORT]
```

Give the project directory positionally after `explore`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is
`uptimely explorer serve [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explore examples/pump_analytics
```

If the build is missing or invalid, the command reports the problem and the
`uptimely project build --project-root ...` recovery command. Scoped builds are
identified in the server output and on the website; spec pages cover the full
model while plan and execution pages cover the selected outputs and their
dependencies.
