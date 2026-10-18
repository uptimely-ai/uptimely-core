# `uptimely explorer`

Build or serve the Analytics Explorer website from spec JSON and a saved
execution plan. Run `uptimely project build` first to create both artifacts.
The CLI renders the selected plan without recompiling it. Use matching spec
and plan artifacts from the same build.

When either input is missing, both commands exit with status `1`, list the
missing file paths, and show a `uptimely project build --project-root ...`
command for the selected project. No inputs are generated automatically and
`serve` does not start the server. This also applies when `_generated` is empty
or absent. Project build creates the standard files; for custom inputs, correct
the `--spec` and `--plan` paths instead.

## `explorer build`

```console
uptimely explorer build \
  [--spec PATH] [--plan PATH] [--output PATH] [--project-root PATH] \
  [--include-generated-at]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--spec PATH` | Conditional | `_generated/spec/spec.json` under `--project-root`; otherwise none | Spec JSON input. Supply this option unless `--project-root` provides the default location. |
| `--plan PATH` | No | `_generated/compile/execution_plan.json` under the project root or current working directory | Saved execution plan input. |
| `--output PATH` | No | `_generated/explorer` under the project root or current working directory | Website output directory. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--include-generated-at` | No | `false` | Include a build timestamp on the spec page when enabled. |

## `explorer serve`

Build the website and serve it for local preview:

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
uptimely project build --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

Explicit input and output paths are relative to the current working directory,
not `--project-root`.
