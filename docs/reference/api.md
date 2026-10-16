# Python API reference

This reference is generated from the package's Python source, type annotations,
and Google-style docstrings. It covers the main interfaces for authoring,
compiling, executing, and inspecting analytics.

For a runnable workflow, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/examples).
The [analytics format reference](../specification/analytics.md) describes
the declarative contract.

## Analytics models and operations

::: uptimely.analytics
    options:
      members:
        - Analytics
        - load_analytics
        - from_python
        - prepare_analytics
        - write_document
        - PreparedAnalytics
        - Entity
        - Dataset
        - Order
        - Dimension
        - Function
        - FunctionCatalog
        - Binding
        - RowContext
        - Call

Canonical contract types live in `uptimely.analytics.model`. `Analytics` contains
only document fields; loading, writing, and semantic preparation are explicit
operations. Derived functions and calls belong to `PreparedAnalytics`, not the
document. See [package boundaries and migration](../overview/architecture.md#analytics-package-boundaries).

## Python authoring

::: uptimely.analytics.python.analytics

::: uptimely.analytics.python.entity

::: uptimely.analytics.python.dataset

::: uptimely.analytics.python.dimension

::: uptimely.analytics.python.feature

::: uptimely.analytics.python.mappings

::: uptimely.analytics.python.bind

::: uptimely.analytics.python.ref

::: uptimely.analytics.python.row_context

::: uptimely.analytics.python.conversion

## Compilation

::: uptimely.compiler
    options:
      members:
        - Compiler
        - CallableGraph
        - CallableNode

## Portable plans

::: uptimely.compiler.plan

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

## Analytics Explorer

::: uptimely.explorer.explorer.Explorer

::: uptimely.explorer.graph_render.GraphStyle

`Explorer.create_html` and the module-level `uptimely.explorer.explorer.create_html`
helper generate the complete static website with analytics, feature graph,
and execution plan pages. Individual HTML report exports are not supported.
`Explorer.create_json` exports reference data; analytics and portable-plan
JSON exports remain available. These outputs describe analytics, not this Python API reference.
See [Analytics Explorer](../components/docs.md).
