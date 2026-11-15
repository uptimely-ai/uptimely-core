# `uptimely export`

Export the packaged HTML, CSS, JavaScript, current Explorer snapshot, and latest
run for ordinary static HTTP hosting. The output can be a directory or a ZIP
file. A `.zip` suffix selects archive output. The generated `config.js` uses a
relative URL for `data/explorer.json`, so the export can live beneath a
documentation site's path prefix. Run information, logs, and profile previews
are saved in `data/run.json` and loaded through a relative URL, without live API
endpoints. Exports made before the first run show an explicit "No saved run"
state.

## Usage

```console
uptimely export [PROJECT_ROOT] --output PATH
```

The command reads and validates the saved snapshot once. It does not start
FastAPI, compile the project, or render pages. Build the project first with
[`uptimely build`](project.md). The same ZIP is available from the local server
at `GET /api/explorer/export`.

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | — | Current working directory | Project root containing the Explorer snapshot. |
| `--project-root PATH` | — | Current working directory | Explicit form of the project directory argument. |
| `--output PATH` |  |  | Output directory or `.zip` archive. Matching files in an existing output directory are replaced. |

## Example

```console
uptimely build example
uptimely run example --preview 10 --log-level debug
uptimely export example --output docs/example
uptimely export example --output cooling-pump-analytics-explorer.zip
```

Export includes the complete saved log and bounded previews. These artifacts may
contain sensitive data. Review them before publishing, and re-export after
running the project to update the hosted results. Invalid or incomplete saved
run artifacts cause export to fail rather than silently omit results.
