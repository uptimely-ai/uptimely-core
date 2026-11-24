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

See [Inspect logs and diagnose failures](../guides/logging.md)
for console output and error details.

<div class="api-reference" markdown="1">

## Command map

| Command | Purpose |
| --- | --- |
| [`uptimely example`](examples.md) | Download runnable example projects. |
| [`uptimely build`](project.md) | Build and publish a complete active bundle. |
| [`uptimely test`](project.md#uptimely-test) | Check the configured project test folder. |
| [`uptimely run`](engine.md) | Run an analytics workflow. |
| [`uptimely explore`](explorer.md) | Preview the Analytics Explorer. |
| [`uptimely export`](export.md) | Export a static Explorer site. |
| [`uptimely feature-graph`](spec.md) | Inspect feature dependencies. |

</div>
