---
hide:
  - toc
---

# Spec

`uptimely.spec` loads, converts, validates, and writes Spec documents. The
compiler turns a Spec into an execution plan.

The [spec format reference](../formats/spec/index.md) describes the
contract. See [Python authoring](../../guides/python/authoring.md) for declarations that produce it, or
[feature graphs](feature-graph.md) for feature dependency analysis.

<div class="api-reference" markdown="1">

## Modules

| Module or subpackage | Purpose |
| --- | --- |
| [api](spec/api.md) | Load a Spec or convert Python declarations. |
| [model](spec/model.md) | Work with Spec document types. |
| [serialization](spec/serialization.md) | Write a Spec as JSON. |
| [validation](spec/validation.md) | Check a Spec and read validation errors. |
| [Python authoring](../../guides/python/authoring.md) | Declare profiles and calculations. |
| [Feature graphs](feature-graph.md) | Inspect feature dependencies. |

## Working with spec

See [Work with Spec documents](../../guides/python/spec-documents.md)
for loading, compilation, and validation examples.

</div>
