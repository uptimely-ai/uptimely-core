# Python API reference

This reference is generated from the package's Python source, type annotations,
and Google-style docstrings. It covers the main interfaces for authoring,
compiling, executing, and inspecting analytics.

For a runnable workflow, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/examples).
The [specification format reference](../specification/specification.md) describes
the declarative contract.

## Specifications

::: uptimely.analytics
    options:
      members:
        - Specification
        - SpecificationParser
        - SpecificationSerializer
        - Entity
        - Dataset
        - Order
        - Dimension
        - Function
        - FunctionCatalog
        - Binding
        - RowContext
        - Call

## Python authoring

::: uptimely.analytics.python.spec

::: uptimely.analytics.python.entity

::: uptimely.analytics.python.dataset

::: uptimely.analytics.python.dimension

::: uptimely.analytics.python.feature

::: uptimely.analytics.python.mappings

::: uptimely.analytics.python.bind

::: uptimely.analytics.python.ref

::: uptimely.analytics.python.row_context

## Compilation

::: uptimely.compile
    options:
      members:
        - Compiler
        - CallableGraph
        - CallableNode

## Portable plans

::: uptimely.plan

## Execution

::: uptimely.engine
    options:
      members:
        - Engine
        - EngineConfig
        - ExecutionResult
        - DataFrameBackend
        - ResourceResolver
        - CallableLoader
        - PolarsBackend
        - PlanResourceResolver
        - EntrypointLoader

## Dependency graphs

::: uptimely.analytics
    options:
      members:
        - FeatureGraph
        - SubGraph
        - GraphStyle

## Analytics Explorer

::: uptimely.explorer.explorer.Explorer

`Explorer.create_html` and the module-level `uptimely.explorer.explorer.create_html`
helper generate the complete static website with specification, feature graph,
and execution plan pages. Individual HTML report exports are not supported.
`Explorer.create_json` exports reference data; specification and portable-plan
JSON exports remain available. These outputs describe analytics, not this Python API reference.
See [Analytics Explorer](../components/docs.md).
