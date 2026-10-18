# `uptimely spec`

The spec CLI provides read-only feature dependency inspection. Spec JSON is
generated as part of the complete bundle by [`uptimely project build`](project.md).

## `spec feature-graph`

```console
uptimely spec feature-graph [--spec PATH] [--project-root PATH] [--features NAME ...] [--verbose]
```

Prints the number of features in the graph. When selected features are given,
also prints the size of their dependency subset. `--verbose` prints the graph
and selected subset as trees.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--spec PATH` | No | `_generated/spec/spec.json` under the project root or current working directory | Spec JSON input. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print graph details when enabled. |
