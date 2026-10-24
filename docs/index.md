# Uptimely Core

Uptimely Core is an open source Python package to manage massive scale numerical calculations with complex dependencies for industrial needs.

The framework standardizes the _atomic components of analytical pipelines_.


Unit | Atomic nature
--- | ---
Feature | Piece of information in a dataset.
Dimension | Feature identifiers.
Dataset | Characterized by dimensions and grain.
Entity | Datasets belonging to same dimension
Function | Data processing unit with strict input and output contracts.


!!! note
    In machine learning, "feature" has a specific meaning. In this framework,
    it is defined more broadly as any metric, KPI, attribute, or property.

The approach enables building reusable components to build advanced analytical flows extremely fast. A well-thought-out structure makes innovation lightning fast for AI agents.

The package has been developed especially for industrial organizations working with machine telemetry, process analytics and factory optimization.


!!! warning
    This project is still under development. APIs and configuration may change
    without notice.


## Capabilities

- Resolve dependencies between features as one global graph
- Calculate results exactly once to avoid duplicate logic
- Column level lineage from Python functions
- Generate automatic documentation
- Generate feature dependency graph
- Extract a subgraph for a single feature
- Clean architecture to isolate components in data pipelines
- Natively support agentic interaction and development

## Examples

See [examples from the repository](https://github.com/uptimely-ai/uptimely-core/tree/main/examples) to see how it works in practice.

Use the [CLI reference](cli/index.md) for commands and options, and the
[Python API reference](python/index.md) for class and function signatures.
