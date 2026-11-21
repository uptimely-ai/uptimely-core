# `uptimely explore`

Preview the Analytics Explorer locally. The server serves the packaged static
frontend and reads the current JSON snapshot on each API request. Use
[`uptimely build`](project.md) to generate or replace the active
project bundle and snapshot before serving it.

## Serve the Explorer

`explore` validates the active build and serves the packaged frontend. It does
not load project source, compile, or prepare presentation data on requests.
Pass `--build` to build and publish once before serving. If the build fails,
the server does not start. This is a one-time build, not a file watcher. A
separate build can publish a new complete snapshot while the server stays up.
Refresh the browser to load it.

```console
uptimely explore \
  [PROJECT_ROOT] [--project-root PATH] [--src-path PATH] [--config CONFIG_OR_PATH] \
  [--build] [--host ADDRESS] [--port PORT]
```

Give the project directory positionally after `explore`, or use
`--project-root PATH`. Do not use both. If omitted, the current working
directory is used.

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | — | Current working directory | Project root containing the active build. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | — | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--config CONFIG_OR_PATH` | — | Root `uptimely.toml`<br>Otherwise built-in defaults | Pass a config name such as `prod` to load `config/prod.toml`, recursively overriding root `uptimely.toml`. Pass a TOML path to load that file alone without merging root settings. Relative paths resolve from the current working directory. Used when `--build` is supplied. |
| `--src-path PATH` | `code.src` | TOML setting if set<br>Otherwise the literal directory name `src` | Python source directory, relative to the project root or given as an absolute path. Used when `--build` is supplied. |
| `--build` | — | Disabled | Build and publish the project bundle before serving. Uses the default full-project build options. |
| `--host ADDRESS` | — | `127.0.0.1` | Address to bind. |
| `--port PORT` | — | `8001` | TCP port. `0` selects an available port. |

Example:

```console
uptimely explore example
uptimely explore example --build
```

If the build is missing or invalid, the command reports the problem and the
`uptimely build --project-root ...` recovery command. A missing or
invalid snapshot is reported by the data API with the same recovery
instruction. Scoped builds are identified in the server output and frontend.
Catalogs cover the full spec while the plan and animation reflect the selected
outputs and their dependencies.
