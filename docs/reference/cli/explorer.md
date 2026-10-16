# `uptimely explorer`

Build or serve the Analytics Explorer website from an analytics JSON document.

## `explorer build`

```console
uptimely explorer build \
  [--analytics PATH] [--output PATH] [--project-root PATH] \
  [--include-generated-at]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--analytics PATH` | Conditional | `_generated/analytics/analytics.json` under `--project-root`; otherwise none | Analytics JSON input. Supply this option unless `--project-root` provides the default location. |
| `--output PATH` | No | `_generated/explorer` under the project root or current working directory | Website output directory. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--include-generated-at` | No | `false` | Include a build timestamp on the analytics page when enabled. |

## `explorer serve`

Build the website and serve it for local preview:

```console
uptimely explorer serve \
  [--analytics PATH] [--directory PATH] [--project-root PATH] \
  [--host ADDRESS] [--port PORT]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--analytics PATH` | No | `_generated/analytics/analytics.json` under the project root or current working directory | Analytics JSON input. |
| `--directory PATH` | No | `_generated/explorer` under the project root or current working directory | Directory for the built website. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--host ADDRESS` | No | `127.0.0.1` | Address to bind. |
| `--port PORT` | No | `8001` | TCP port; `0` selects an available port. |

Example:

```console
uptimely explorer serve --project-root examples/pump_analytics
```
