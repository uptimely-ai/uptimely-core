# `uptimely spec feature-graph`

The `spec feature-graph` command provides read-only feature dependency
inspection. Spec JSON is generated as part of the complete bundle by
[`uptimely project build`](project.md).

## Usage

```console
uptimely spec feature-graph [PROJECT_ROOT] [--spec PATH] [--project-root PATH] [--features NAME ...] [--verbose]
```

Prints the number of features in the feature graph. When selected features are
given, also prints the size of their feature dependency subset. `--verbose`
prints the feature graph and selected subset as trees.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | No | Current working directory | Root for resolving defaults and importing function entrypoints. May be passed as `--project-root PATH` instead. |
| `--spec PATH` | No | Spec in the validated active build | Inspect a separate Spec JSON file instead of the active build's saved spec. |
| `--project-root PATH` | No | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--features NAME ...` | No | All features | Select output features and their feature dependencies. |
| `--verbose` | No | `false` | Print feature-graph details when enabled. |

Without `--spec`, the command reads the saved spec from the validated active
build. If no valid build exists, it reports the recovery command; run
`uptimely project build --project-root ...` to create or replace the build.
