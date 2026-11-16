# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building project bundles, inspecting feature dependencies, running analytics
workflows, and previewing the Analytics Explorer.

Commands use one top-level action followed by its arguments. Project-specific
commands accept an optional project directory immediately after the action
name, such as `uptimely build example`. If omitted, the current working
directory is used. `--project-root PATH` is also supported as an explicit
alternative. Do not pass both forms.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

Each command reference lists an option's default and matching `uptimely.toml`
setting, if one exists. A dash means there is no corresponding setting. If both
the TOML setting and Default cells are blank, the argument is required.

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

<div class="api-reference" markdown="1">

## Command map

| Command | Purpose |
| --- | --- |
| [`uptimely example`](examples.md) | Download runnable example projects. |
| [`uptimely build`](project.md) | Build and publish a complete active bundle. |
| [`uptimely run`](engine.md) | Run an analytics workflow. |
| [`uptimely explore`](explorer.md) | Preview the Analytics Explorer. |
| [`uptimely export`](export.md) | Export a static Explorer site. |
| [`uptimely feature-graph`](spec.md) | Inspect feature dependencies. |

</div>
