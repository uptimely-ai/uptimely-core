# Inspect logs and diagnose failures

## Console logging

CLI logs use `LEVEL | MESSAGE` columns, with an 8-character-wide level field.
Package and module names are omitted from console output. Internal logger names
remain unchanged. Leading blank lines are removed from messages, while intentional
multiline content such as trees, tables, previews, and tracebacks remains
intact. Long single-line terminal messages wrap to the terminal width, with
continuation lines aligned under the message column. Redirected output remains
unwrapped. `NO_COLOR` disables coloring without disabling terminal wrapping.
Build, compiler, spec-validation, and execution traces use flat messages
rather than section headers and indented bullets. Execution-stage invocation
messages are also unindented.
Spec operator-reference checks identify the operator, its target profile, and
the referenced resource. Dimension-parent and profile-grain checks identify the
dimension, resolution, or profile being checked.
Dataframe checks name the producing operator, function, invocation, and profile
for fragments, or the accumulated profile or merge result for datasets. Column
checks include the expected column names and declared types.
Vectorize-result checks also identify the invocation and list the output,
existing, or allowed columns relevant to each check.
Tables, feature trees, and dataframe previews retain their structured layouts.
Semantic spec validation logs `Start spec validation` at info level before
checking the spec and `Spec validated` only after successful validation.
Command failures use `ERROR    | MESSAGE` on stderr with exit code 1.
Argument-parser errors use the same error prefix. Commands supporting
`--log-level debug` also show the full chained exception traceback, including
source filenames and line numbers. Other log levels retain concise errors.

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
It does not enable validation. Use `--validate` to run the runtime checks.
Execution debug logs use flat messages with the logger's module name,
rather than headers, indentation, or bullets. For example:

```text
DEBUG    | Check fragment dataframe type
DEBUG    | Merging into profile pump_profile
```

Module prefixes identify where each message originates. Invocation start messages
identify the operator, function, binding role, and result handling.
Structured logs use the invocation IDs from the saved plan. Newly compiled
plans use [compact invocation IDs](../artifacts/execution-plan.md#invocations).
Rebuild the project to adopt them.

## Preview logging

Previews show all columns and omit the Polars shape line. They are logged after
the completion summary and processed-profile summary, before any debug details.
Levels above `info` hide previews, the completion summary, and processed-profile
details.

See the [`uptimely build`](../cli/project.md) and
[`uptimely run`](../cli/engine.md) references for command options.
