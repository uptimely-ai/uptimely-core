# Python API reference

This reference is generated from the package's Python source, type annotations,
and Google-style docstrings. It covers the main interfaces for authoring,
compiling, executing, and inspecting analytics.

For a runnable workflow, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/examples).
The [specification format reference](../specification/specification.md) describes
the declarative contract.

## Specifications

::: uptimely.spec
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

::: uptimely.spec.python_spec.spec

::: uptimely.spec.python_spec.entity

::: uptimely.spec.python_spec.dataset

::: uptimely.spec.python_spec.dimension

::: uptimely.spec.python_spec.feature

::: uptimely.spec.python_spec.mappings

::: uptimely.spec.python_spec.bind

::: uptimely.spec.python_spec.ref

::: uptimely.spec.python_spec.row_context

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

::: uptimely.docs.docs.Documentation

`Documentation.create_html` and the module-level `uptimely.docs.docs.create_html`
helper generate the complete static website with specification, feature graph,
and execution plan pages. Individual HTML report exports are not supported.
`Documentation.create_json` exports reference data; specification and portable-plan
JSON exports remain available. These outputs describe analytics, not this Python API reference.
See [analytics documentation](../components/docs.md).
