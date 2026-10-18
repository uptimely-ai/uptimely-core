# `uptimely explorer`

Preview the Analytics Explorer locally. The explicit `explorer build` command
has been removed; use [`uptimely project build`](project.md) to generate all
project artifacts.

## `explorer serve`

During this migration checkpoint, `serve` still renders the website from
standalone spec and execution-plan files before starting the preview server.
The next Explorer migration step will make it serve the website saved in the
active project bundle.

```console
uptimely explorer serve \
  [--spec PATH] [--plan PATH] [--directory PATH] [--project-root PATH] \
  [--host ADDRESS] [--port PORT]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--spec PATH` | No | `_generated/spec/spec.json` under the project root or current working directory | Spec JSON input. |
| `--plan PATH` | No | `_generated/compile/execution_plan.json` under the project root or current working directory | Saved execution plan input. |
| `--directory PATH` | No | `_generated/explorer` under the project root or current working directory | Directory for the built website. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explorer serve --project-root examples/pump_analytics
```

Explicit input and output paths are relative to the current working directory,
not `--project-root`.
