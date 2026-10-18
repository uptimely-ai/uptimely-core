# `uptimely explorer`

Preview the saved Analytics Explorer website locally. Use
[`uptimely project build`](project.md) to generate or replace the active
project bundle before serving it.

## `explorer serve`

`serve` validates and serves the website from the active build. It does not
load source files, compile, render, or modify build artifacts. The active-build
read lock remains held while the server is running, so a rebuild cannot replace
the website until the server exits.

```console
uptimely explorer serve \
  [--project-root PATH] [--host ADDRESS] [--port PORT]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Project root containing the active build. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explorer serve --project-root examples/pump_analytics
```

If the build is missing or invalid, the command reports the problem and the
`uptimely project build --project-root ...` recovery command. Scoped builds are
identified in the server output and on the website; spec pages cover the full
model while plan and execution pages cover the selected outputs and their
dependencies.
