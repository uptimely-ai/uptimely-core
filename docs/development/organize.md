# Organizing analytics projects

This page introduces three ways to organize analytical projects.

## Centralized

Keep the spec declarations and analytical functions in a monorepo layout. This is the simplest starting point and matches the runnable examples.

The end-to-end example uses this layout (supporting files are omitted):

```text
project/
├── functions/
│   ├── source.py
│   └── calculation.py
├── config/
│   ├── engine.json
│   └── spec/
│       └── spec.py
└── _generated/
    └── build/
        ├── build.json
        ├── spec.json
        ├── execution_plan.json
        └── explorer/
```

Keep functions in simple modules initially. Split them into packages when their
size or reuse warrants it, and distribute shared code as a versioned package when
multiple projects depend on it.

## Clustered

Keep multiple independent workflows in one or multiple repositories.

Each workflow contains its independent spec definition and active build bundle.

Share reusable implementations through packages rather than mixing the workflows'
generated output.

## Decentralized

!!! caution
    Automatic composition of spec documents from multiple repositories is not
    supported. This pattern requires project-specific assembly tooling.

A master project brings multiple scattered spec repositories and their
spec documents together in one place. Each contributing repository maintains its
own analytical code and spec document. The master project assembles those
definitions into unified spec, making dependencies across repositories
visible and allowing the combined system to be documented, compiled, and executed.

The master project records which repositories and versions contribute to the
system. Its combined spec document is generated from those contributions rather
than maintained as a separate copy of every team's definitions.
