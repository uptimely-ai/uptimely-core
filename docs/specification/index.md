# Open Analytics Specification

The Open Analytics Specification describes an analytical system in a single JSON
document. It connects the data model, reusable function templates, and feature
dependencies in a shared contract that tools can validate, document, and compile.

Read the [format reference](specification.md) for the document structure and
semantic rules.

## What the specification enables

- Declare an analytical system in one document rather than scattering its
  definitions across scripts.
- Reuse function templates while keeping their implementations separate from
  the declarations.
- Resolve feature dependencies into an execution plan that avoids duplicate
  calculations.
- Generate documentation and feature-level lineage from the same definitions
  used to compile analytics.

## Logical layer

Stored values describe the physical data, but do not necessarily explain its
analytical meaning. Consider a table containing two features at two steps:

| Step | Feature | Value |
| --- | --- | --- |
| 1 | A | 10 |
| 1 | B | 8 |
| 2 | A | 11 |
| 2 | B | 17 |

The rows alone do not tell a consumer what `A` and `B` represent, how they were
produced, or which downstream calculations depend on them. The same values can
also support different business definitions, reports, and decisions.

The specification provides a logical layer alongside the physical data. It
declares feature identities, their dependencies, and the operations that produce
them. Those definitions connect source inputs to consumption-ready information
without requiring consumers to reconstruct the entire workflow from database
tables and implementation code.

## Result validation

Logical dependencies help teams review whether an analytical design matches its
intended meaning. Consumers and developers can ask:

- Which source and calculated features are required to produce a result?
- Which functions transform those inputs?
- Are the dependencies consistent with the intended business definition?

This review complements numerical tests and data-quality checks; a dependency
graph alone does not prove that calculated values are correct. It makes the
declared relationships visible so teams can check that the intended variables
and transformations are combined.

## Feature dependency graph

The [feature dependency graph](../artifacts/feature-graph.md) visualizes the
logical relationships between fragments, calculated features, and functions.
It shows how values are derived and which downstream features depend on them,
making the specification's logical layer easier to explore and review.
