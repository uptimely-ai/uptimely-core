# `uptimely explorer`

Preview the Analytics Explorer locally. The server serves the packaged static
frontend and reads the current JSON snapshot on each API request. Use
[`uptimely project build`](project.md) to generate or replace the active
project bundle and snapshot before serving it.

The shortcut `uptimely explore` serves the same frontend with the same
options as `uptimely explorer serve`.

## `explorer serve`

`serve` validates the active build and serves the packaged frontend. It does
not load project source, compile, or prepare presentation data on requests.
Pass `--build` to build and publish once before serving; if the build fails,
the server does not start. This is a one-time build, not a file watcher. A
separate build can publish a new complete snapshot while the server stays up;
refresh the browser to load it.

```console
uptimely explore \
  [PROJECT_ROOT] [--project-root PATH] [--build] [--host ADDRESS] [--port PORT]
```

Give the project directory positionally after `explore`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is
`uptimely explorer serve [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--build` | No | Disabled | Build and publish the project bundle before serving. Uses the default full-project build options. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explore examples/pump_analytics
uptimely explore examples/pump_analytics --build
```

If the build is missing or invalid, the command reports the problem and the
`uptimely project build --project-root ...` recovery command. A missing or
invalid snapshot is reported by the data API with the same recovery
instruction. Scoped builds are identified in the server output and frontend;
catalogs cover the full spec while the plan and animation reflect the selected
outputs and their dependencies.
