# `uptimely spec`

The spec CLI provides read-only feature dependency inspection. Spec JSON is
generated as part of the complete bundle by [`uptimely project build`](project.md).

## `spec feature-graph`

```console
uptimely spec feature-graph [PROJECT_ROOT] [--spec PATH] [--project-root PATH] [--features NAME ...] [--verbose]
```

Prints the number of features in the graph. When selected features are given,
also prints the size of their dependency subset. `--verbose` prints the graph
and selected subset as trees.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Root for resolving defaults and importing function entrypoints. May be passed as `--project-root PATH` instead. |
| `--spec PATH` | No | Spec in the validated active build | Inspect a separate Spec JSON file instead of the active build's saved spec. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print graph details when enabled. |

Without `--spec`, the command reads the saved spec from the validated active
build. If no valid build exists, it reports the recovery command; run
`uptimely project build --project-root ...` to create or replace the build.
