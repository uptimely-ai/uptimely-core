# Analytics project structure

This page shows a recommended project layout for a single analytics project built with Uptimely Core.

## Suggested structure

A practical setup keeps source data, Python declarations, and generated artifacts
separate. This minimal layout follows the end-to-end example; supporting modules
are omitted:

```text
project/
├── data/
├── functions/
│   ├── source.py
│   └── calculation.py
├── config/
│   ├── engine.json
│   └── analytics/
│       ├── analytics.py
│       ├── dataset_<name>.py
│       ├── entity.py
│       ├── dimension.py
│       └── functions.py
└── _generated/
    ├── analytics/
    │   └── analytics.json
    └── compile/
        └── execution_plan.json
```

## Folder responsibilities

- data: raw or reference datasets used by the analytics workflow.
- functions: reusable source, calculation, and write functions.
- config/analytics: Python declarations that define entities, datasets, and relationships.
- _generated: output created by the tooling, such as exported analytics JSON, compiled plans, graphs, and documentation.
- config/engine.json: engine settings and bind values used to resolve runtime placeholders.

This separation keeps the project easy to reason about: analytics declarations
live in config, runtime logic lives in functions, and generated resources stay
clearly separate from source inputs.

The [end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/pump_analytics/README.md) uses CLI commands
for analytics export, compilation, execution, documentation, and feature
graphs. `uptimely analytics export --module <module>` imports a module exposing
`python_analytics`, a `PythonAnalytics` instance, and writes JSON.
`uptimely explorer build` writes a linked website to `_generated/explorer/`.
All HTML pages are generated together by that command.
Analytics and plan JSON exports live in `_generated/analytics/` and
`_generated/compile/`; `uptimely analytics feature-graph` prints graph summaries and,
with `--verbose`, dependency trees without writing HTML.
The [smaller Python example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/simple_analytics/README.md) demonstrates
analytics export without the full compilation and execution workflow.
