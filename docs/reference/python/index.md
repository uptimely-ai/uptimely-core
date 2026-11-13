# Python API reference

Find Python interfaces for authoring, building, and running analytics. The
reference pages show the public classes and functions, grouped by package.

| Need | Reference |
| --- | --- |
| Declare profiles and calculations | [Python authoring](python.md) |
| Load, validate, and write a Spec | [Spec](spec.md) |
| Build or load a project bundle | [Projects](project.md) |
| Compile and serialize an execution plan | [Compiler and plans](compiler.md) |
| Run analytics and read results | [Execution engine](engine.md) |
| Inspect feature dependencies | [Feature graphs](feature-graph.md) |
| Prepare Explorer data | [Explorer](explorer.md) |
| Load Python functions | [Python entrypoints](entrypoint.md) |
| Read local or S3 files | [Storage](storage.md) |
| Use row windows in calculations | [Row context](row-context.md) |
| Review shared argument and operator types | [Spec vocabulary](spec-vocabulary.md) |

Common classes are available from `uptimely`, including `Spec`, `Project`,
`Compiler`, and `Engine`. CLI commands and MCP tools have separate references.

For a complete example, see the
[repository examples](https://github.com/uptimely-ai/uptimely-core/tree/main/example).
The [architecture overview](../../architecture/index.md) explains how the
packages work together.
