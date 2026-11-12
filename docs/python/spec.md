# Spec

`uptimely.spec` loads, converts, validates, and writes Spec documents. The
compiler turns a Spec into an execution plan.

The [spec format reference](../architecture/spec.md) describes the
contract. See [Python authoring](python.md) for declarations that produce it, or
[feature graphs](feature-graph.md) for feature dependency analysis.

<div class="api-reference" markdown="1">

## Modules

| Module or subpackage | Purpose |
| --- | --- |
| [api](spec/api.md) | Load a Spec or convert Python declarations. |
| [model](spec/model.md) | Work with Spec document types. |
| [serialization](spec/serialization.md) | Write a Spec as JSON. |
| [validation](spec/validation.md) | Check a Spec and read validation errors. |
| [Python authoring](python.md) | Declare profiles and calculations. |
| [Feature graphs](feature-graph.md) | Inspect feature dependencies. |

## Working with spec

Load or convert a Spec with [api](spec/api.md), then pass it to the
[compiler](compiler.md) to make an execution plan. The module-level helpers
are also available as `uptimely.spec.load_spec` and `uptimely.spec.from_python`.

</div>
