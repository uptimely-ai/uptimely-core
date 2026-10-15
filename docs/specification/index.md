# About analytics

Analytics describes an analytical system in a single JSON document. It connects
the data model, reusable function templates, and feature dependencies in one
contract that tools can validate, document, and compile.

Read the [analytics reference](analytics.md) for the document structure and
semantic rules.

The [compiler](compiler.md) turns analytics into a portable execution plan; the
[execution engine](engine.md) runs that plan against runtime data.

## What analytics enables

- Declare an analytical system in one document rather than scattering its
  definitions across scripts.
- Reuse function templates while keeping their implementations separate from
  the declarations.
- Resolve feature dependencies into an execution plan that avoids duplicate
  calculations.
- Generate documentation and feature-level lineage from the same definitions
  used to compile analytics.
