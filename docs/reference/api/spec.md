# Spec

`uptimely.spec` owns declarative documents, loading, conversion, semantic
validation, serialization, and feature dependency inspection. Executable
invocations and execution plans belong to the compiler.

The [spec format reference](../../components/spec.md) describes the
contract. See [Python authoring](python.md) for declarations that produce it, or
[feature graphs](feature-graph.md) for dependency analysis.

<div class="api-reference" markdown="1">

## Package map

| Module or subpackage | Purpose |
| --- | --- |
| [api](spec/api.md) | Load and convert spec with semantic validation. |
| [model](spec/model.md) | Define the spec document, datasets, bindings, and function metadata. |
| [json](spec/json.md) | Write spec documents as JSON. |
| [validation](spec/validation.md) | Check document relationships and inspect structured validation errors. |
| [python](python.md) | Author spec using Python declarations. |
| [feature_graph](feature-graph.md) | Inspect feature dependencies and select subgraphs. |

## Working with spec

1. Load a JSON document or convert Python declarations using
   [api](spec/api.md).
2. Work with the document types defined in [model](spec/model.md).
3. Inspect dependencies using [feature graphs](feature-graph.md), or pass the
   document to the [compiler](compiler.md) to create executable invocations.
4. Write the spec document using [json](spec/json.md). After editing a document
   directly, call [validate_spec](spec/validation.md) to check its semantics again.

Public convenience imports such as `uptimely.spec.Spec` and
`uptimely.spec.load_spec` remain available. The reference pages
document each interface in its defining module.

</div>
