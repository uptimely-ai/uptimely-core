# Command-line reference

The `uptimely` command provides project utilities for downloading examples,
building project bundles, inspecting feature dependencies, running analytics
workflows, and previewing the Analytics Explorer.

For common tasks, use the top-level shortcuts `uptimely build`, `uptimely run`,
and `uptimely explore`. The grouped forms `uptimely project build`,
`uptimely engine run`, and `uptimely explorer serve` remain available and accept
the same options. Project-specific commands accept an optional project
directory immediately after the action name, such as
`uptimely build example`. If omitted, the current working
directory is used. `--project-root PATH` is also supported as an explicit
alternative; do not pass both forms.

Run `uptimely --help` or `uptimely <command> --help` to see the options
available in an installed version.

CLI logs use `LEVEL | MESSAGE` columns, with an 8-character-wide level field.
Package and module names are omitted from console output; internal logger names
remain unchanged. Leading blank lines are removed from messages, while intentional
multiline content such as trees, tables, previews, and tracebacks remains
intact. Long single-line terminal messages wrap to the terminal width, with
continuation lines aligned under the message column. Redirected output remains
unwrapped; `NO_COLOR` disables coloring without disabling terminal wrapping.
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
source filenames and line numbers; other log levels retain concise errors.

<div class="api-reference" markdown="1">

## Command map

| Command | Reference | Purpose |
| --- | --- | --- |
| `uptimely spec feature-graph` | [Spec feature-graph](spec.md) | Inspect feature dependencies. |
| `uptimely engine` | [Engine](engine.md) | Run an analytics workflow. |
| `uptimely examples` | [Examples](examples.md) | Download runnable example projects. |
| `uptimely explorer` | [Explorer](explorer.md) | Preview or export the Analytics Explorer. |
| `uptimely project` | [Project](project.md) | Build and publish a complete active bundle. |
| `uptimely build` | [Project build](project.md) | Shortcut for `uptimely project build`. |
| `uptimely run` | [Engine run](engine.md) | Shortcut for `uptimely engine run`. |
| `uptimely explore` | [Explorer serve](explorer.md) | Shortcut for `uptimely explorer serve`. |

## Typical workflow

From an installed package, download examples and build the complete active
bundle, including its spec, execution plan, and Explorer data snapshot:

```console
uptimely examples
uptimely build example
```

Run the saved execution plan from the active build:

```console
uptimely run example
```

The command defaults and options are documented on each command page. Project
build consumers use the active bundle under `_generated/build/`; rebuild it
with `uptimely build` (or `uptimely project build`) to change the saved plan or
feature scope. The `uptimely-mcp` server is a separate optional command. See
[MCP API](../mcp/index.md) for installation and client setup.

</div>
