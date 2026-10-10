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
        - Dimension
        - Function
        - FunctionCatalog
        - Binding
        - Call

## Python authoring

::: uptimely.spec.python_spec.spec

::: uptimely.spec.python_spec.entity

::: uptimely.spec.python_spec.dataset

::: uptimely.spec.python_spec.dimension

::: uptimely.spec.python_spec.feature

::: uptimely.spec.python_spec.fragment

::: uptimely.spec.python_spec.bind

::: uptimely.spec.python_spec.ref

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

## Analytics documentation

::: uptimely.docs.docs.Documentation

These methods generate documentation for an analytics specification, not this
Python API reference. See [automatic documentation](../artifacts/automatic-documentation.md).
