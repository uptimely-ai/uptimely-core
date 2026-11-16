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
tracks the spec and execution plan. The snapshot is published separately at
`artifacts/explorer.json`.

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
| `--src-path PATH` | `application.src_path` | TOML setting if set<br>Otherwise the literal directory name `src` | Python source directory, relative to the project root or given as an absolute path. Overrides the configured value for this command. |
| `--python-spec MODULE:ATTRIBUTE` | `application.python_spec` | TOML setting if set<br>Otherwise discover standard sources | Select an importable Python attribute containing a `Spec` instance. The project root and configured source directory are added while loading it. Mutually exclusive with `--json-spec`. |
| `--json-spec PATH` | `application.json_spec` | TOML setting if set<br>Otherwise discover standard sources | Select source spec JSON. Mutually exclusive with `--python-spec`. Explicit CLI paths are relative to the current working directory. Configured paths are relative to the project root. |
| `--features FEATURE ...` | — | All features | Select one or more output features and their required dependencies. |
| `--log-level LEVEL` | — | `info` | Set Uptimely logging to `debug`, `info`, `warning`, `error`, or `critical`. Debug includes build duration, output folder, spec source, resource counts, and plan size. |

### Build logging

By default, a successful build logs `Build files created to {path}`.
Warnings and errors remain visible. Use `--log-level debug` for a summary table
printed after the build debug trace and before the final success message,
grouped into:

- **Build:** duration in seconds, output folder, and feature scope.
- **Spec:** source identifier and numbers of functions, profiles, and features.
- **Plan:** numbers of execution stages and invocations.

Build logs stream as the build runs. Failed builds do not print a success summary.

Duration covers building, validating, and publishing the bundle, not workflow
execution. Spec counts cover the complete specification, including for scoped
builds. Features are counted per profile, excluding dimensions. Plan counts
describe the compiled feature scope. The source identifier is the original JSON
path or Python module entrypoint, not the generated spec export.

### Build behavior

Building may import Python declarations and inspect function signatures, but it
does not execute workflow functions or sinks. Python module-level code still
runs when a declaration or function module is imported. Build only trusted
project sources. A successful full or scoped build replaces the previous
active bundle. Source edits do not change an existing build. Rebuild explicitly
to publish updated artifacts. If building fails, the last successful bundle
remains active.
Rebuilding after changing callable contracts, operator bindings, or descriptive
function categories regenerates the plan and Explorer snapshot. It does not
execute analytical functions or sinks.
