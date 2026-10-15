# Project architecture

Uptimely Core separates authoring, analytics, planning, and execution into
distinct layers. Each layer has a different responsibility and a different
level of portability.

## Layer Hierarchy

```mermaid
flowchart LR
    subgraph resources["Produced resources and definitions"]
        python_analytics["Python analytics"]
        json_analytics["Analytics JSON"]
        plan["Execution plan"]
        result["Analytical results"]
    end

    subgraph actions["Actions"]
        parse["Export Python analytics"]
        compile["Compile analytics"]
        execute["Execute plan"]
    end

    python_analytics -->|input to| parse
    parse -->|produces| json_analytics
    json_analytics -->|input to| compile
    compile -->|produces| plan
    plan -->|input to| execute
    execute -->|produces| result

    classDef resource fill:#e8f1fb,stroke:#2563eb,stroke-width:1px
    classDef action fill:#fff3cd,stroke:#b7791f,stroke-width:1px

    class python_analytics,json_analytics,plan,result resource
    class parse,compile,execute action
```

```text
Python analytics -> Export Python analytics -> Analytics JSON -> Compile analytics -> Execution plan -> Execute plan -> Execution result
```

Python authoring is optional. It is a developer-friendly definition that may be
written in Python and then converted into the authoritative Analytics JSON.

**The Analytics JSON is the definitive declarative contract**: it describes
the data and calculations the analytical system needs without prescribing every
operational step for producing them. The compiler turns that contract into a
portable execution plan. The plan defines what runs, in what order, and under
which declared execution context. The engine reads the plan and executes it
against live runtime state.

## Python Authoring

Python authoring is a definition layer for analytics.

It lets developers describe analytics with Python objects, imports,
helpers, reuse, and editor support. This is useful when a project wants a
maintainable source format for larger analytics definitions or generated fragments.

Python authoring is not the authoritative runtime document. Its purpose is to
produce the same analytics structure that could also be written directly as
JSON.

Use Python authoring when developers want autocomplete and type checking,
repeated analytics patterns, or a higher-level authoring format that exports
to JSON.

For enterprise setup, source metadata may be scattered across systems. Python
can read it and generate the standard Analytics JSON document.

## Python-to-Analytics conversion

This step reads Python declarations and produces the equivalent Analytics
JSON document so that the result can be validated, documented, and compiled.

## Analytics JSON

The Analytics JSON document is the source of truth for the definitions.

It is the portable contract for an analytics workflow. It describes entities,
datasets, dimensions, function catalogs, feature registries, mappings,
bindings, and engine hints in a format that does not depend on Python
authoring code. Physical fragments are created by compilation and belong to
the compiler and engine, not the analytics definition.

The analytics document uses primitive function and argument data type
definitions, so it is agnostic of tools and programming languages.

Other tools should treat the Analytics JSON as the source of truth. Documentation,
validation, graph generation, compilation, and execution should all be possible
from this document.

Keep the Analytics JSON document under version control, such as Git.

## Compiler

The compiler is an action that turns the definitive Analytics JSON document into a
portable execution plan.

It decides what runs, in what order, and under which declared execution
context. It builds the callable graph, resolves dependencies, creates execution
stages, records callable metadata, and can export the plan as a document.

The compiled plan should be portable. It should describe the intended execution
without depending on one specific in-memory engine implementation.

The compiler resolves structural references such as `$datasets.@`,
`$features.<id>`, and `$dimensions.<id>` into identifiers.
It does not resolve runtime values such as loaded dataframes or physical storage
locations; those are left as `?<namespace>.<object>.<attribute>` placeholders for
the engine to resolve. The engine binds physical implementation variables at
runtime according to the function template's primitive argument types.

Version 0.1 declares `polars` as the only supported dataframe backend. The
compiled plan records that executable claim as `required_backend`, and the
engine validates compatibility at runtime. Orchestration is outside the
analytics and plan contracts.

Separated definition, planning and execution enables versatile use cases. In
cloud environments with unlimited resources, it may be possible to execute the
whole global plan on one engine. Another lightweight engine can execute a subset
of features in restricted environments.

## Plan

The plan is a definition produced by the compiler.

It is a portable description of the workflow that specifies what should run, in
what order, and under which declared execution context. The plan is not a live
runtime object; it is the formalized outcome of compilation.

A stage is a dependency layer within that plan. It groups operations that can run
in the same wave because they do not depend on one another. The compiler builds a
callable dependency graph where nodes are operations and edges represent upstream
feature or dataset dependencies. It then asks the graph for its parallel
bottom-up topological order, which yields layered execution groups. Each layer is
serialized as a stage in the plan, and the engine later resolves those stage IDs
back into executable operations.

This gives the plan both a deterministic execution order and a clear boundary for
parallel execution inside a single stage. In practice, stage 1 contains the
independent source and preparation work, stage 2 contains calculations whose
inputs are now available, and later stages continue until the downstream writes
and final outputs are reached.

## Engine

The engine reads the plan and executes it.

It loops through the plan stages, runs each operation, stores produced
runtime data, and makes results available to dependent operations. It resolves
compiled dataset and feature identifiers into runtime objects such as
dataframes and dimension-keyed calculated feature results.

The Python engine resolves `?<namespace>.<object>.<attribute>` runtime
placeholders (such as `?storage.telemetry_source.path`) against engine `bind`
supplied when the engine is constructed. This is how a compiled plan runs against
different physical storage locations in different environments without
recompiling Analytics JSON.

The engine in this repository executes plans with Python functions and the
Polars backend. Its runtime state is returned as an execution result containing
datasets, calculated outputs, operation statuses, durations, failures, and the
plan version.

## Responsibility Boundary

The main boundary is between definitions and actions.

Definitions describe the intended state of the system:

- Python authoring (definition)
- Analytics JSON (definition)
- Plan (definition)

Actions transform or execute those definitions:

- Python-to-Analytics conversion (action)
- Compiler (action)
- Engine (action, reads plan and executes)

```text
Python authoring (definition) -> Python-to-Analytics conversion (action) -> Analytics JSON (definition)
Analytics JSON (definition) -> Compiler (action) -> Plan (definition)
Plan (definition) -> Engine (action, reads plan and executes)
```

This separation keeps the Analytics JSON stable, the compiler deterministic,
and engine implementations replaceable.
