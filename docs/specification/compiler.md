# Specification compiler

The compiler turns an [Open Analytics specification](index.md) into a portable
execution plan. It connects declared feature requirements to function calls,
resolves their dependencies, and schedules the resulting operations into stages.

Compilation prepares a workflow but does not run its analytical functions. The
portable plan is the boundary between planning and execution: an
[execution engine](engine.md) loads the plan and runs it against runtime data.

## Compilation workflow

The built-in Python compiler:

1. Uses an in-memory specification or loads one from a JSON file.
2. Builds a callable dependency graph from the declared bindings.
3. Selects the required dependency closure when a feature subset is requested.
4. Resolves structural references into portable operation arguments and records
   each operation's dependencies.
5. Groups operations into dependency-ordered stages.
6. Copies the runtime resources and callable signatures needed by the plan.

The compiler reads signatures by importing the declared Python entrypoints.
Their modules and dependencies must therefore be importable in the compilation
environment, even though compilation does not invoke the analytical functions.
Missing entrypoints or unreadable signatures cause compilation to fail.

## Compiling a plan

`Compiler` accepts a `Specification` object or a JSON specification path as a
string or `Path`. Calling `compile()` returns an `ExecutionPlan`.

```python
from uptimely.compile import Compiler
from uptimely.spec import Specification

specification = Specification.from_json("_generated/spec/spec.json")
plan = Compiler(specification).compile()
plan.export_json("_generated/compile/execution_plan.json")
```

To compile directly from a file:

```python
plan = Compiler("_generated/spec/spec.json").compile()
```

## Compiling a feature subset

The compiler can produce a feature subset. The requested features form the
starting points of a dependency closure, so the plan includes their required
dataframe-producing mappings, calculated-feature dependencies, and writes for the
selected datasets.

```python
plan = Compiler(
    specification,
    features=["health_signal_normalized"],
).compile()
```

Pass a collection of feature identifiers, not a single string. The compiler
includes their transitive prerequisites and the writes configured for the
selected datasets; subset compilation does not create a calculation-only
workflow. A retained sink that needs features outside the selected closure may
fail during execution.

Subset plans retain configured dataset writes and do not trim literal
feature lists passed to those write functions. Declare all required features
as mapping inputs; an operation that requests a feature outside the selected
closure can fail because that value was not materialized.

## Dependency resolution

Explicit mapping inputs define feature dependencies. The compiler uses those
edges to include required producers in a feature-subset plan and to order
operations. Feature or dataset identifiers passed as arguments do not, by
themselves, declare a calculated-feature dependency. A dataset dataframe
argument requires its source observations, but not every calculated feature
available in that dataset; list each consumed feature as an input.

Vectorize and write inputs belong to their owning dataset. Other operation
categories can transfer data between datasets when the mapping declares those
inputs. Independent mappings can be scheduled in the same stage.

The compiler requires an acyclic execution graph. Semantic validation checks
that feature dependencies have valid producers and ownership, bindings refer
to known function categories and arguments, and row-context dimensions and
order declarations are consistent. Structural validation rejects unknown
fields and malformed declarations. The compiler also checks bound argument
names and explicit selector/type agreement; it does not validate or coerce
arbitrary literal values against declared types. These checks cannot infer
hidden data dependencies inside a function or establish that its calculations
are correct. Test function implementations together with the mappings that
declare them.

## Compilation and runtime boundaries

Structural references such as `$features.<id>`, `$datasets.@`, and
`$dimensions.<id>` describe relationships in the specification. The compiler
resolves them to identifiers in the plan; the engine binds those identifiers to
live dataframes and feature values.

The `@` dataset reference names the owning dataset, not its final completed
state. The compiler makes the mapping's declared inputs available first. A
single-output `$features.@.id` reference can only be used when the mapping has
one calculated output. Dataset `.id` references are metadata; they do not add
feature dependencies. Structural selector types must agree with their declared
argument types, but the compiler does not check arbitrary literal values or
confirm that the implementation accepts them.

Runtime placeholders such as `?storage.telemetry_source.path` remain in the
compiled arguments. The engine resolves them against its `bind` mapping,
allowing a plan to run with different physical storage locations without
recompilation.

The built-in compiler records `polars` as the required backend. The engine checks
that claim at runtime. Deployment and orchestration are outside the compiler's
responsibility.

Row-context metadata is preserved separately from operation arguments. When any
operation declares context, planned datasets' ordering and row scopes are
included under `resources.datasets`, so an exported plan does not need the
original specification to interpret those requirements. Context is local to
each binding; the compiler does not infer transitive retention across chained
calculations. Calculated-feature context is read from the feature declaration,
not copied through its binding or derived call.

## Generated execution plan

An execution plan describes the workflow without retaining the compiler's live
dependency graph. An engine can load it without loading or recompiling the
original specification. An alternative engine may use another language or
runtime, provided it implements the plan contract and supports the declared
backend.

The serialized plan contains these top-level fields:

| Field | Meaning |
| --- | --- |
| `plan_version` | Version of the portable plan format. |
| `specification_version` | Version of the specification used to create the plan. |
| `required_backend` | Backend required by the plan. Version 0.1 uses `polars`. |
| `resources` | Runtime metadata needed by an engine, including dimensions, entities, function templates, and signatures. |
| `operations` | The executable operations in the dependency graph. |
| `stages` | Lists of operation identifiers grouped by dependency level. |

The compiler copies only the information needed at runtime into `resources`.
The plan carries callable entrypoints and binding arguments, but remains
distinct from the authoring specification.

### Operations

Each operation represents one callable invocation:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for the operation in the plan. |
| `kind` | Operation category: `read`, `conform`, `expand`, `collapse`, `vectorize`, or `write`. |
| `entrypoint` | Required callable implementation location, including for collapse functions. |
| `entity_id` | Entity whose dimensions and datasets scope the operation. |
| `dataset_id` | Dataset receiving or supplying the operation's dataframe state. |
| `output` | Operation output identifier, such as a calculated feature. |
| `arguments` | Portable compiled argument values. Structural references are resolved to identifiers; runtime dataframe binding is deferred to the engine. |
| `dependency_ids` | Operation identifiers that must complete before this operation. |
| `row_context` | Mapping input-context requirements; `null` when undeclared. Stored separately from function arguments. |

Every data-producing operation returns a dataframe with its declared outputs.
Write operations consume the assembled dataset state. The plan records
operation contracts and dependencies; it does not execute them.

### Execution stages

The compiler derives stages from the callable graph topology. A stage contains
operations whose prerequisites are in earlier stages or have no remaining
prerequisites. Operations in a later stage cannot run until their dependencies
have completed.

For example, a dataset may produce this topology:

```text
Stage 1: read telemetry
Stage 2: vectorize bearing temperature maximum
Stage 3: vectorize normalized health signal
Stage 4: write pump results
```

Independent operations may appear in the same stage. The built-in Python
engine currently processes stage members sequentially, but another engine may
run independent operations in parallel while preserving the dependency order.

Stages are represented in JSON by operation identifiers rather than duplicated
operation objects:

```json
"stages": [
	["callable:example:pump:read"],
	["callable:example:pump:health_signal_normalized"],
	["callable:example:pump:write"]
]
```

The exact identifiers depend on the entity, dataset, operation, and function
declarations in the source specification.

## Exporting and executing a plan

An exported plan can be inspected, transferred, or executed later without
recompiling the specification:

```python
from uptimely.engine import Engine
from uptimely.plan import ExecutionPlan

plan = ExecutionPlan.from_json("_generated/compile/execution_plan.json")
result = Engine(plan).execute()
```

`ExecutionPlan` exposes serialized operations and resolved execution stages.
To inspect operation order and dependencies in HTML, generate the full website
from the original specification:

```python
from uptimely.docs import docs

index_path = docs.create_html(specification)
```

`uptimely docs build` provides the same website. Its execution-plan section
has Overview, Graph, and Stages pages. The Graph page defaults to 2D and provides
a 2D/3D selector without navigating away. Both views use compiled callable operations and their
dependency edges; feature lineage is shown separately under Feature graph.
Standalone plan HTML export is not supported; portable-plan JSON export and
loading do not require website generation.

The overview summarizes callable, function, entity, and feature counts, along
with stages, dependency edges, and the largest number of operations in a stage.
Bar charts show the operation-type breakdown and each stage's size. Stage size
indicates potential parallelism, not how many operations the engine actually
runs concurrently.

The [execution engine](engine.md) describes how the built-in runtime executes
the plan and accumulates dataframes. The plan contract is separate from any one
engine implementation or orchestration environment.

## Create your own compiler

The built-in compiler is a reference implementation, not a required part of every
deployment. You can create another compiler to target a different execution
environment or apply backend-specific planning strategies while retaining the
[specification](index.md) as the source of truth.

Start by deciding which engine will consume the output. A compiler targeting the
built-in engine must produce its existing execution plan contract. A compiler
that emits another format needs a corresponding engine or adapter; changing the
output format alone does not make it executable by the built-in engine.

For a compatible compiler:

1. Parse and validate the specification without changing the meaning of its
   bindings, features, and dimensions.
2. Resolve the dependency graph, including upstream dependencies and dataset
   writes when supporting feature subsets.
3. Generate operations with unique identifiers, implementation entrypoints,
   portable arguments, output identifiers, and explicit dependency identifiers.
4. Schedule every operation exactly once, placing each dependency in an earlier
   stage than the operation that consumes it.
5. Include the resources required by the target engine and declare the plan
   version, specification version, and required backend accurately.
6. Preserve runtime placeholders for the engine rather than embedding
   environment-specific storage locations during compilation.

In Python, reuse the `Operation`, `Plan`, and `ExecutionPlan` models exported by
`uptimely.plan`. The built-in `Compiler.compile()` implementation shows how
dependency resolution, operation construction, signature inspection, and resource
export fit together. Reuse those concepts rather than depending on its private
methods as an extension API.

Validate exported plans by loading them through `ExecutionPlan.from_json()`.
The loader checks operation identifiers, dependency references, and stage
ordering, but those structural checks do not establish semantic equivalence.
Also test the compiler with representative specifications, feature subsets, and
the target engine to verify that it produces the intended numerical results.

The built-in engine currently supports only `polars`; another backend needs an
engine that implements it. A compiler may be written in another language, as
long as its output meets the chosen engine's plan contract.
