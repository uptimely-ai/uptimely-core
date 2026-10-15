# Organizing analytics

This page introduces three ways to organize analytical projects.

## Centralized

Keep the analytics declarations and analytical functions in the same
repository. This is the simplest starting point and matches the runnable examples.

The end-to-end example uses this layout (supporting files are omitted):

```text
project/
├── functions/
│   ├── source.py
│   └── calculation.py
├── config/
│   ├── engine.json
│   └── analytics/
│       └── analytics.py
└── _generated/
    ├── analytics/
    └── compile/
```

Python declarations in `config/analytics/` are exported to `_generated/analytics/analytics.json`.
The compiler produces `_generated/compile/execution_plan.json`, and the engine
executes the plan.
Functions describe the read, transformation, and write logic; CLI commands
coordinate export, compilation, and execution. Export a module exposing a
`python_analytics` with `uptimely analytics export --module <module>`, then use
`uptimely plan build` and `uptimely engine run`. See the
[examples guide](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/README.md)
for runnable commands.

Source datasets and other generated artifacts are described in the
[project structure guide](project-structure.md). See the
[end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/pump_analytics/README.md) for the complete layout.

Keep functions in simple modules initially. Split them into packages when their
size or reuse warrants it, and distribute shared code as a versioned package when
multiple projects depend on it.

## Clustered

Keep multiple independent workflows in one or multiple repositories, each using the centralized layout:

```text
projects/
├── pump_analytics/
│   ├── functions/
│   ├── config/
│   └── _generated/
└── factory_analytics/
    ├── functions/
    ├── config/
    └── _generated/
```

Each workflow exports its own analytics and compiles its own plan.
Share reusable implementations through packages rather than mixing the workflows'
generated output.

## Decentralized

!!! caution
    Automatic composition of specifications from multiple repositories is not
    supported. This pattern requires project-specific assembly tooling.

A master project brings multiple scattered analytics repositories and their
specifications together in one place. Each contributing repository maintains its
own analytical code and analytics document. The master project assembles those
definitions into unified analytics, making dependencies across repositories
visible and allowing the combined system to be documented, compiled, and executed.

The master project records which repositories and versions contribute to the
system. Its combined analytics document is generated from those contributions rather
than maintained as a separate copy of every team's definitions.

```text
master-project/
├── config/
│   └── analytics/
│       └── sources.json
└── _generated/
    ├── analytics/
    │   └── analytics.json
    └── compile/
```

```text
analytics-package/
├── pyproject.toml
├── src/
│   └── analytics_functions/
│       ├── __init__.py
│       └── calculation.py
└── config/
    └── analytics/
        └── analytics.json
```

In this illustrative layout, `sources.json` is a project-defined manifest of
contributing repositories, versions, and specification locations; it is not a
configuration format supported by Uptimely. Each analytics repository contributes its
`config/analytics/analytics.json`, either authored directly or exported from Python declarations.

Project-specific assembly tooling retrieves those specifications, combines their
definitions, and resolves identifier conflicts and cross-repository references.
It produces one complete `_generated/analytics/analytics.json` analytics document for Uptimely to load.
Uptimely does not discover repositories or merge analytics documents
automatically.

Install the packages containing the declared entrypoints in both the compilation
and execution environments. Keep their function declarations in sync with the
implementations and validate the assembled analytics document and compiled plan in CI.
Centralizing the definitions does not require moving all analytical source code
into the master repository.
The engine consumes the resulting plan, not the source analytics documents.
