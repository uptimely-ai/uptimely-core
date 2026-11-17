# `uptimely feature-graph`

The `feature-graph` command provides read-only feature dependency
inspection. Spec JSON is generated as part of the complete bundle by
[`uptimely build`](project.md).

## Usage

```console
uptimely feature-graph [PROJECT_ROOT] [--spec PATH] [--project-root PATH] [--features NAME ...] [--log-level LEVEL]
```

Prints the number of features in the feature graph. When selected features are
given, also prints the size of their feature dependency subset. Set
`--log-level debug` to print the feature graph and selected subset as trees.

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | — | Current working directory | Root for resolving defaults and importing function entrypoints. May be passed as `--project-root PATH` instead. |
| `--spec PATH` | — | Spec in the validated active build | Inspect a separate Spec JSON file instead of the active build's saved spec. This option does not use `application.json_spec`, which selects the source for builds. |
| `--project-root PATH` | — | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--features NAME ...` | — | All features | Select output features and their feature dependencies. |
| `--log-level LEVEL` | — | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug prints the feature graph and selected subset as trees. |

Without `--spec`, the command reads the saved spec from the validated active
build. If no valid build exists, it reports the recovery command. Run
`uptimely build --project-root ...` to create or replace the build.
