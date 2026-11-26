# `uptimely build`

Build the generated resources for an analytics project.

```console
uptimely build [PROJECT_ROOT] \
  [--project-root PATH] [--src-path PATH] [--config CONFIG_OR_PATH] \
  [--python-spec MODULE:ATTRIBUTE | --json-spec PATH | --yaml-spec PATH] \
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
| `--python-spec MODULE:ATTRIBUTE` | `application.python_spec` | TOML setting if set<br>Otherwise discover standard sources | Select an importable Python attribute containing a `Spec` instance. The project root and configured source directory are added while loading it. Mutually exclusive with other source options. |
| `--json-spec PATH` | `application.json_spec` | TOML setting if set<br>Otherwise discover standard sources | Select source spec JSON. Relative paths resolve from the project root. Mutually exclusive with other source options. |
| `--yaml-spec PATH` | `application.yaml_spec` | TOML setting if set<br>Otherwise discover standard sources | Select a YAML file or directory. Relative paths resolve from the project root. Mutually exclusive with other source options. |
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

## `uptimely test`

```console
uptimely test [PROJECT_ROOT] [--project-root PATH] [--config CONFIG_OR_PATH] \
  [--build] [--show] [--log-level LEVEL]
```

The command reads JSON files from `test.path`, defaulting to `tests/uptimely`
relative to the project root. Absolute paths are also supported. The project
directory and config options follow the same rules as `uptimely build`.
The command uses the saved plan and bundled source, not live project source,
and requires a build containing project source. Pass `--build` to publish a
full project build using the selected configuration before testing. If that
build fails, tests do not run and the previous test report remains unchanged.
Pass `--show` to print all input rows and expected output rows as dataframes for
each case, including failed cases. Tables appear side by side when they fit and
stack otherwise. Wide tables are split into column panels with row numbers
repeated for each panel. Long column names and values wrap within their cells.
For mismatches, the expected and actual output are also compared with `!`
marking differing or missing values. Comparison follows the same row order and
floating-point tolerance as the test. The side-by-side input and output display
does not imply that rows correspond. Strings and control characters are shown
using JSON escapes. Output is independent of the log level and may contain
sensitive fixture or actual data.

Name each file `<profile_id>.json`. Each top-level key is an operator ID, with
one or more named `cases`. `inputs` maps dataframe argument names to rows.
`expected.return` contains the complete returned rows. Other binding arguments
come from the saved plan and selected project configuration.

```json
{
  "operator_id": {
    "cases": {
      "basic": {
        "inputs": {"dataset": [{"value": 2.0}]},
        "expected": {"return": [{"value": 2.0, "result": 4.0}]}
      }
    }
  }
}
```

Inputs must have at least one row and the same columns in each row. Dataframe
types are inferred from JSON. Output rows are compared in order, ignoring
column order and dataframe types, with Polars' default floating-point tolerance.
An empty expected array checks for no rows, not column names or types.

Only compute bindings returning dataframes are supported. Reader, writer, and
workflow cases are rejected. Test cases do not run upstream operators or merges.
Functions still execute Python code and are not sandboxed. Test only trusted
builds, and keep side effects out of the selected functions.

The command saves the latest outcomes, errors, timestamps, and build fingerprint
to `artifacts/test/test.json`. Case inputs, expected and actual outputs, and
resolved calls are saved in `artifacts/test/cases/<profile_id>.json`, grouped
by operator and case. A call records its function entrypoint and arguments
before execution. Dataframe arguments are shown as `$<argument name>`, such as
`$dataset`, in `call.arguments`. The `call.dataframe_inputs` field maps their
JSON Pointers to names in `inputs`. Only paths in that mapping represent
dataframe inputs, so literal strings that look like input markers remain
distinguishable. Earlier case artifacts may use `null`, `$input`, or
`$input.<name>` at those paths. If arguments cannot be resolved or recorded, the
case reports an error without a call. A call remains available if the function
or output comparison fails. Actual output is saved when the returned dataframe
can be collected and serialized. Case artifacts and Explorer exports may
contain sensitive configuration values and case data.
The report uses format version 4. Explorer also reads versions 1, 2, and 3.

The fingerprint covers the build manifest, Spec, and plan, but not bundled code
bytes. The command does not change `artifacts/run/` and exits with
status 0 when all cases pass and 1 for failed cases or invalid setup. At least
one case is required.
