# `uptimely project`

Build the generated resources needed to inspect or execute an analytics project.

## `project build`

```console
uptimely project build \
  [--project-root PATH] [--entrypoint MODULE:ATTRIBUTE | --analytics PATH]
```

The command runs two stages, in order:

1. Build and validate analytics JSON at `_generated/analytics/analytics.json`.
2. Compile it into `_generated/compile/execution_plan.json`.

Both paths are beneath the project root, or the current directory when no root
is supplied. Missing output directories are created. Each invocation rebuilds
both artifacts; there is no freshness check or cache.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Root for source discovery, importing project functions, and generated output paths. |
| `--entrypoint MODULE:ATTRIBUTE` | No | Discover standard sources | Select a Python attribute containing a `PythonAnalytics` instance. Mutually exclusive with `--analytics`. |
| `--analytics PATH` | No | Discover standard sources | Select source analytics JSON. Mutually exclusive with `--entrypoint`. Relative to the current working directory. |

Source discovery follows [`analytics build`](analytics.md#analytics-build):
`config/analytics/analytics.py` or `config/analytics/analytics.json`. If both
exist, an explicit selection is required.

```console
uptimely project build --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

Building imports Python declarations and inspects function signatures, but does
not execute the workflow, read input datasets, or invoke analytics functions.
It does not build Explorer HTML or generate engine configuration. The engine
uses the saved plan with runtime configuration supplied separately.
Importing Python modules does execute their module-level code; only build trusted
project sources.

To execute the saved plan without recompiling:

```console
uptimely engine run --project-root examples/pump_analytics --compile false
```

Failures identify the stage and exit nonzero. Later stages do not run after a
failure. The build is not transactional: if compilation fails, the newly built
analytics JSON remains and any previous plan is not removed. Treat a failed build
as incomplete; fix the error and rerun before using its outputs.

Individual commands remain available:

```console
uptimely analytics build --project-root examples/pump_analytics
uptimely plan build --project-root examples/pump_analytics
```
