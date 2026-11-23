# Inspect logs and diagnose failures

## Console logging

CLI messages use `LEVEL | MESSAGE` columns. The level field is 8 characters
wide. Package and module names are hidden in console output, but the internal
logger names are unchanged.

### Diagnostic messages

Build, compiler, spec-validation, and execution traces use flat messages rather
than section headers and indented bullets. Execution-stage invocation messages
are also unindented.

Validation messages identify the relevant declarations and data:

- **Spec checks**
  - Operator references: operator, target profile, and resource.
  - Dimension parents and profile grains: dimension, resolution, or profile.
- **Dataframe checks**
  - Fragments: producing operator, function, invocation, and profile.
  - Datasets: accumulated profile or merge result.
  - Columns: expected names and declared types.
- **Vectorize results:** invocation and relevant output, existing, or allowed
  columns.

Tables, feature trees, and dataframe previews retain their structured layouts.
Semantic Spec validation logs `Start spec validation` at info level before
checking the Spec. It logs `Spec validated` only after validation succeeds.

### Errors

Command failures are written to stderr with the `ERROR    | MESSAGE` prefix
and exit code 1. Argument-parser errors use the same prefix. Commands that
support `--log-level debug` also show the full chained exception traceback,
including source filenames and line numbers. Other log levels show concise
errors.

## Build logging

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

## Execution logging

At info level, the CLI announces the start of the engine run. With `--build`,
it also announces the project-bundle build before building it. Successful runs
log individual processed-profile details first, followed by
`Engine processed X profiles in Y s.` The engine scope is not logged.
After a successful run and any requested previews, an info log shows the
`uptimely explore --project-root PATH` command for opening that project's Explorer.

The log level applies to Uptimely loggers, not third-party dependency loggers.
It does not enable analytical validation, which is not currently supported.
Execution debug logs use flat messages with the logger's module name,
rather than headers, indentation, or bullets. For example:

```text
DEBUG    | Executing invocation read (pump_io:read)
```

Module prefixes identify where each message originates. Invocation start messages
identify the invocation and entrypoint.
Structured logs use the invocation IDs from the saved plan. Newly compiled
plans use compact invocation IDs shown in the
[execution plan](../artifacts/execution-plan.md).
Rebuild the project to adopt them.

See the [`uptimely build`](../cli/project.md) and
[`uptimely run`](../cli/engine.md) references for command options.
