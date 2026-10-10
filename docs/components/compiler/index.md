# Compiler

The compiler translates an [Open Analytics specification](../../specification/index.md)
into a portable execution plan. It resolves declared dependencies, creates
operations from function bindings, and organizes those operations into execution
stages.

Compilation prepares the workflow; it does not run the analytical operations.
The resulting plan is the hand-off format to an [engine](../engine/index.md), which
loads it and executes the operations against runtime data.

## Compilation workflow

The built-in Python compiler:

1. Uses an in-memory specification or loads one from a JSON file.
2. Builds a callable dependency graph from the declared bindings.
3. Selects the required dependency closure when a feature subset is requested.
4. Resolves structural references into portable operation arguments and records
   each operation's dependencies.
5. Groups operations into stages based on the graph topology.
6. Records runtime resource metadata and callable return signatures in the plan.

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

specification = Specification.from_json("generated/spec/spec.json")
plan = Compiler(specification).compile()
plan.export_json("generated/compile/execution_plan.json")
```

To compile directly from a file:

```python
plan = Compiler("generated/spec/spec.json").compile()
```

## Compiling a feature subset

The compiler can produce a feature subset. The requested features form the
starting points of a dependency closure, so the plan includes their required
fragment operations, calculated-feature dependencies, and writes for the
selected datasets.

```python
plan = Compiler(
    specification,
    features=["health_signal_normalized"],
).compile()
```

Pass a collection of feature identifiers, not a single string. Subset compilation
includes the owning datasets' writes; it does not create a calculation-only
workflow. A sink that requires features outside the subset may fail at execution
time.

## Compilation and runtime boundaries

Structural references such as `$features.<id>`, `$datasets.@`, and
`$dimensions.<id>` describe relationships in the specification. The compiler
resolves them to identifiers in the plan; the engine binds those identifiers to
live dataframes and feature values.

Runtime placeholders such as `?storage.telemetry_source.path` remain in the
compiled arguments. The engine resolves them against its `runtime_resources`,
allowing a plan to run with different physical storage locations without
recompilation.

The built-in compiler records `polars` as the required backend. The engine checks
that claim at runtime. Deployment and orchestration are outside the compiler's
responsibility.

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

The compiler copies only the specification information required at runtime
into `resources`. The plan therefore carries the implementation entrypoints
and binding arguments needed to invoke operations, but it is not a replacement
for the authoring specification.

### Operations

Each operation represents one callable invocation:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for the operation in the plan. |
| `kind` | Operation category: `read`, `conform`, `expand`, `collapse`, `vectorize`, or `write`. |
| `entrypoint` | Implementation location used by the selected engine. |
| `entity_id` | Entity whose dimensions and datasets scope the operation. |
| `dataset_id` | Dataset receiving or supplying the operation's dataframe state. |
| `output` | Operation output identifier, such as a calculated feature. |
| `arguments` | Portable compiled argument values. Structural references are resolved to identifiers; runtime dataframe binding is deferred to the engine. |
| `dependency_ids` | Operation identifiers that must complete before this operation. |

Fragment operations return dataframes. Vectorize operations return one feature
element, which the engine materializes as the declared output column. Write
operations consume the assembled dataset state. The plan records these
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

plan = ExecutionPlan.from_json("generated/compile/execution_plan.json")
result = Engine(plan).execute()
```

`ExecutionPlan` exposes the serialized operations, resolved execution stages,
and a flat execution-order view. It also supports exporting a human-readable
HTML report for inspecting operation order and dependencies:

```python
plan.export_html("generated/compile/execution_plan.html")
```

The [Engine documentation](../engine/index.md) describes how the built-in engine
executes the loaded plan and accumulates runtime dataframes. The plan itself
remains independent of that engine's dataframe implementation and orchestration
environment.

## Create your own compiler

The built-in compiler is a reference implementation, not a required part of every
deployment. You can create another compiler to target a different execution
environment or apply backend-specific planning strategies while retaining the
[specification](../../specification/index.md) as the source of truth.

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

The current built-in engine supports only `polars`; targeting another backend
requires an engine that supports it. An alternative compiler can be written in
another language, provided its output meets the chosen engine's contract.
