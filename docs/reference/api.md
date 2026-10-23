# Python API reference

Browse the API by its location under `src/uptimely/`. Each package page groups
classes and functions by their defining module, with signatures, parameters,
and return values generated from the Python source.

<div class="api-reference" markdown="1">

## Package map

| Package or module | Reference | Purpose |
| --- | --- | --- |
| `uptimely.project` | [Projects](api/project.md) | Load project specs and build or read active build bundles. |
| `uptimely.spec` | <span id="spec-models-and-operations"></span>[Spec](api/spec.md) | Load, validate, prepare, and serialize spec definitions. |
| `uptimely.spec.python` | <span id="python-authoring"></span>[Python authoring](api/python.md) | Declare spec using Python classes and helpers. |
| `uptimely.spec.feature_graph` | <span id="dependency-graphs"></span>[Feature graphs](api/feature-graph.md) | Inspect dependencies and select feature subgraphs. |
| `uptimely.spec.validation` | [Spec validation](api/spec/validation.md) | Validate document relationships and handle structured errors. |
| `uptimely.compiler` | <span id="compilation"></span><span id="portable-plans"></span>[Compiler and plans](api/compiler.md) | Compile spec and read or write portable plans. |
| `uptimely.engine` | <span id="execution"></span>[Execution engine](api/engine.md) | Execute plans with configurable runtime adapters. |
| `uptimely.explorer` | <span id="analytics-explorer"></span>[Analytics Explorer](api/explorer.md) | Generate an analytics website. |
| `uptimely.row_context` | [Row context](api/row-context.md) | Describe row windows passed to analytical functions. |
| `uptimely.entrypoint` | [Python entrypoints](api/entrypoint.md) | Load Python callables and inspect their signatures. |
| `uptimely.storage` | [Storage](api/storage.md) | Read local files and S3 objects through a shared interface. |
| `uptimely.spec.operations` | [Spec vocabulary](api/spec-vocabulary.md) | Inspect operations, return kinds, and operation rules. |
| `uptimely.spec.arg_types` | [Spec vocabulary](api/spec-vocabulary.md) | Inspect atomic and recursive argument types. |
| `uptimely.spec.selectors` | [Spec vocabulary](api/spec-vocabulary.md) | Inspect structural reference prefixes and selectors. |

## Finding the right interface

- **Author a spec definition:** start with [Python authoring](api/python.md)
  or the [spec format reference](../components/spec.md).
- **Load or prepare a definition:** use the
  [spec operations](api/spec/api.md).
- **Compile and run it:** use the [compiler](api/compiler.md), then the
  [engine](api/engine.md).
- **Inspect or publish it:** use [feature graphs](api/feature-graph.md) and
  [Explorer](api/explorer.md).

The pages follow the source layout rather than repeating package-level
re-exports. Public convenience imports such as `uptimely.spec.Spec`
and `uptimely.engine.Engine` remain available.

This reference covers public Python interfaces, including exported types,
constants, and validation functions. Internal resolution, runtime-state, and
rendering helpers are not included. CLI command handlers and MCP server internals
are also outside its scope.

For a runnable workflow, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/examples).
The [architecture overview](../overview/architecture.md) explains how the
packages fit together.

</div>
