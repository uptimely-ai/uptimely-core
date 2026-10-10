# Analytics project structure

This page shows a recommended project layout for a single analytics project built with Uptimely Core.

## Suggested structure

A practical setup keeps source data, Python declarations, and generated artifacts
separate. This minimal layout follows the end-to-end example; supporting modules
and additional runner scripts are omitted:

```text
project/
├── data/
├── functions/
│   ├── source.py
│   └── calculation.py
├── spec/
│   ├── spec.py
│   └── datasets/
├── generated/
│   ├── spec/
│   │   └── spec.json
│   └── compile/
│       └── execution_plan.json
├── runtime-resources.json
├── run_export_spec.py
├── run_execution_plan.py
└── run_engine.py
```

## Folder responsibilities

- data: raw or reference datasets used by the analytics workflow.
- functions: reusable source, calculation, and write functions.
- spec: Python declarations that define entities, datasets, and relationships.
- generated: output created by the tooling, such as exported JSON specifications, compiled plans, graphs, and documentation.
- runtime-resources.json: environment-specific values used to resolve runtime placeholders.
- run_*.py: entry points for specification export, compilation, and execution.

This separation keeps the project easy to reason about: the code that defines the model lives in the spec folder, the runtime logic lives in functions, and generated resources stay clearly separate from source inputs.

The [end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/example_1/README.md) also has documentation
and feature-graph runners, writing to `generated/docs/` and `generated/graph/`.
The [smaller Python example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/example_2/README.md) demonstrates
specification export without the full compilation and execution workflow.
