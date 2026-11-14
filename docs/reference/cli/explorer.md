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
  [PROJECT_ROOT] [--project-root PATH] [--src-path PATH] [--build] [--host ADDRESS] [--port PORT]
```

Give the project directory positionally after `explore`, or use
`--project-root PATH`; do not use both. If omitted, the current working
directory is used. The grouped form is
`uptimely explorer serve [PROJECT_ROOT]`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the active build. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--src-path PATH` | No | `src` | Python source directory, relative to the project root or given as an absolute path. Used when `--build` is supplied. |
| `--build` | No | Disabled | Build and publish the project bundle before serving. Uses the default full-project build options. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explore example
uptimely explore example --build
```

If the build is missing or invalid, the command reports the problem and the
`uptimely project build --project-root ...` recovery command. A missing or
invalid snapshot is reported by the data API with the same recovery
instruction. Scoped builds are identified in the server output and frontend;
catalogs cover the full spec while the plan and animation reflect the selected
outputs and their dependencies.

## `explorer export`

Export the packaged HTML, CSS, JavaScript, current Explorer snapshot, and latest run for
ordinary static HTTP hosting. The output can be a directory or a ZIP file;
`.zip` selects archive output. The generated `config.js` uses a relative URL
for `data/explorer.json`, so the export can live beneath a documentation
site's path prefix. Run information, logs, and profile previews are saved in
`data/run.json` and loaded through a relative URL, without live API endpoints.
Exports made before the first run show an explicit "No saved run" state.

```console
uptimely explorer export [PROJECT_ROOT] --output PATH
```

The command reads and validates the saved snapshot once. It does not start
FastAPI, compile the project, or render pages. Build the project first with
`uptimely project build`. The same ZIP is available from the local server at
`GET /api/explorer/export`.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Project root containing the Explorer snapshot. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. |
| `--output PATH` | Yes | — | Output directory or `.zip` archive. Matching files in an existing output directory are replaced. |

Example:

```console
uptimely project build example
uptimely run example --preview 10 --log-level debug
uptimely explorer export example --output docs/example
uptimely explorer export example --output cooling-pump-analytics-explorer.zip
```

Export includes the complete saved log and bounded previews. These artifacts may
contain sensitive data; review them before publishing. Re-export after running
the project again to update the hosted results. Invalid or incomplete saved run
artifacts cause export to fail rather than silently omit results.
