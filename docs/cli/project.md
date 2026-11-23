# `uptimely build`

Build the generated resources for an analytics project.

```console
uptimely build [PROJECT_ROOT] \
  [--project-root PATH] [--src-path PATH] [--config CONFIG_OR_PATH] \
  [--python-spec MODULE:ATTRIBUTE | --json-spec PATH] \
  [--features FEATURE [FEATURE ...]] [--log-level LEVEL]
```

The project directory may be given positionally or with `--project-root`, but
not both. If omitted, the current working directory is used.

The command validates the complete source specification, compiles one execution
plan, and prepares a versioned Explorer data snapshot. The active build manifest
tracks all three. The snapshot is published with the bundle at
`artifacts/build/explorer.json`.

### Feature selection

The spec export always contains the complete model. If `--features` is
provided, the plan includes the selected outputs, their dependencies, and the
associated profile sinks. The Explorer snapshot contains that exact plan
alongside the complete spec model. Omit `--features` to compile all features.
Selections must be nonempty and valid. Duplicate names are normalized.

### Options

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_ROOT` | — | Current working directory | Project directory for source discovery and generated output paths. The project root and source directory are importable during the build. May be passed as `--project-root PATH` instead. |
| `--project-root PATH` | — | Current working directory | Explicit form of the project directory argument. Cannot be combined with positional `PROJECT_ROOT`. |
| `--config CONFIG_OR_PATH` | — | Root `uptimely.toml`<br>Otherwise built-in defaults | Pass a config name such as `prod` to load `config/prod.toml`, recursively overriding root `uptimely.toml`. Pass a TOML path to load that file alone without merging root settings. Relative paths resolve from the current working directory. |
| `--src-path PATH` | `code.src` | TOML setting if set<br>Otherwise the literal directory name `src` | Python source directory, relative to the project root or given as an absolute path. Overrides the configured value for this command. |
| `--python-spec MODULE:ATTRIBUTE` | `application.python_spec` | TOML setting if set<br>Otherwise discover standard sources | Select an importable Python attribute containing a `Spec` instance. The project root and configured source directory are added while loading it. Mutually exclusive with `--json-spec`. |
| `--json-spec PATH` | `application.json_spec` | TOML setting if set<br>Otherwise discover standard sources | Select source spec JSON. Mutually exclusive with `--python-spec`. Relative CLI and configured paths are resolved from the project root. |
| `--features FEATURE ...` | — | All features | Select one or more output features and their required dependencies. |
| `--log-level LEVEL` | — | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes build duration, output folder, spec source, resource counts, and plan size. |

### Build logging

See [Build logging](../guides/logging.md#build-logging)
for progress messages and debug summaries.

### Build behavior

Building validates the Spec, imports Python declarations and function entrypoints
for signature inspection, and compiles the execution plan. It does not execute
workflow functions or sinks. Python module-level code still runs when a
declaration or function module is imported. Build only trusted project sources. A successful full or scoped build replaces the previous
active bundle. Source edits do not change an existing build. Rebuild explicitly
to publish updated artifacts. If building fails, the last successful bundle
remains active.
Rebuilding after changing callable contracts, operator bindings, or descriptive
function categories regenerates the plan and Explorer snapshot. It does not
execute analytical functions or sinks.
