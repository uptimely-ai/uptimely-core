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
│   └── spec/
│       ├── spec.py
│       ├── dataset_<name>.py
│       ├── entity.py
│       ├── dimension.py
│       └── functions.py
└── _generated/
    ├── spec/
    │   └── spec.json
    ├── compile/
    │   └── execution_plan.json
    └── explorer/
        ├── index.html
        ├── spec/
        ├── plan/
        └── execution/
```

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/` | Raw or reference datasets used by the analytics workflow. |
| `functions/` | Reusable source, calculation, and write functions. |
| `config/spec/` | Python declarations that define entities, datasets, and relationships. |
| `_generated/` | Output created by the tooling, such as exported specification JSON, compiled plans, graphs, and documentation. |
| `config/engine.json` | Engine settings and bind values used to resolve runtime placeholders. |

This separation keeps the project easy to reason about: specification declarations
live in config, runtime logic lives in functions, and generated resources stay
clearly separate from source inputs.

The fixed project structure enables automation of repetitive setup and tooling
while preserving flexibility in the analytics implementation.

The [end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/pump_analytics/README.md) uses CLI commands
for spec export, compilation, execution, documentation, and feature
graphs. `uptimely spec build --project-root <project>` discovers
`config/spec/spec.py` or `config/spec/spec.json` and writes
validated JSON. Python sources expose `python_spec`, a `PythonSpec`
instance. Use `--entrypoint <module>:<attribute>` or `--spec <path>` to select a source
explicitly; this is required when both standard sources exist.
`uptimely explorer build` writes a linked website to `_generated/explorer/`.
All HTML pages are generated together by that command.
Spec and plan JSON exports live in `_generated/spec/` and
`_generated/compile/`; `uptimely spec feature-graph` prints graph summaries and,
with `--verbose`, dependency trees without writing HTML.
The [smaller Python example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/simple_analytics/README.md) demonstrates
spec export without the full compilation and execution workflow.
