---
hide:
  - toc
---

# Python API reference

Find Python interfaces for authoring, building, and running analytics. The
reference pages show the public classes and functions, grouped by package.

| Need | Reference |
| --- | --- |
| Declare profiles and calculations | [Python authoring](python.md) |
| Load, validate, and write a Spec | [Spec](spec.md) |
| Work with a configured project | [Application](application.md) |
| Build or load a project bundle | [Builds and bundles](build.md) |
| Compile a Spec | [Compiler](compiler.md) |
| Inspect and serialize execution plans | [Models](plans-models.md) and [serialization](plans-serialization.md) |
| Run analytics and read results | [Execution engine](engine.md) |
| Read saved run metadata and previews | [Saved runs](engine-runs.md) |
| Inspect feature dependencies | [Feature graphs](feature-graph.md) |
| Prepare Explorer data | [Explorer](explorer.md) |
| Load Python functions | [Python entrypoints](entrypoint.md) |
| Read local or S3 files | [Storage](storage.md) |
| Use row windows in calculations | [Row-context utilities](row-context.md) |
| Review shared argument and operator types | [Operator bindings](spec-vocabulary.md), [argument types](vocabulary-arguments.md), and [selectors](vocabulary-selectors.md) |

Common classes are available from `uptimely`, including `Spec`, `Uptimely`,
`Compiler`, and `Engine`. CLI commands and MCP tools have separate references.

For a complete example, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/example).
The [application overview](../intro/application.md) explains how the
packages work together.
