# Compiler and plans

`uptimely.compiler` creates an execution plan from a loaded Spec.
`uptimely.execution_plan` reads and writes plans. An action describes how a
function is used; the plan records that work for the engine to run.

Load a Spec with `uptimely.spec.load_spec` (or create one with
`uptimely.spec.from_python`), then compile it:

```python
from uptimely import compiler, execution_plan, spec

specification = spec.load_spec("spec.json")
plan = compiler.Compiler().compile(specification, features=["health_signal_normalized"])
execution_plan.export_json(plan, "execution_plan.json")
```

Compilation checks the Spec before creating the plan. Use
`execution_plan.export_json` to save it and `execution_plan.from_json` to load
it. Version 1 and 2 plans are not supported; rebuild the bundle from its source
Spec.

Each invocation carries the runtime contract needed without consulting the Spec:
`id_columns` lists target keys, `column_types` maps typed target columns to logical
types, and `argument_types` maps declared argument names to their types. The
compiler takes key types from canonical dimension declarations, ahead of any
local feature metadata. These fields survive plan serialization. Saved plans
without them must be rebuilt; loading reports a recompile error rather than
running without key or type information.

Plans cache `invocations_by_id` and `execution_stages`, along with resource
indexes: `function_ids`, `entity_ids`, `datasets` (dataset ID to entity ID),
`arguments` (invocation ID to bound arguments), `features` (output feature ID to
producing invocations), `calculated_features`, `entrypoints`, and
`invocations_by_kind`, and `count_per_kind` (invocation counts keyed and sorted by
function kind). Output features include dimension outputs; the Spec
remains the source of feature metadata. Repeated reads reuse the same indexes.
Treat them and their nested containers as read-only. For changes, create a new plan
with `dataclasses.replace`; construction validates its execution contracts and
cached properties are computed afresh.
Indexes do not change the portable JSON format.

Compiler responsibilities are separated by module: `compiler` orchestrates plan
construction through its `graph`, `execution_stages`, `invocations`, `entrypoints`,
`packages`, `signatures`, `stages`, and `resources` properties in fail-fast order.
`signature_resources` and `entrypoint_packages` serialize the two individual
resource mappings; `resources` combines them for the portable plan.
The `features` attribute retains the collection passed to `compile()`. Compilation
rejects a bare string; graph selection deduplicates identifiers in input order.
Build properties are cached for one compilation and reset on every `compile()`
call, including retries after failure. Access them only after supplying a Spec
through `compile()`; treat their results as read-only. A compiler instance supports
sequential reuse, not concurrent compilations. The compiler properties collect
entrypoints, package provenance, and signatures directly. `function_signatures`
validates each enabled function once; `signatures` maps those cached results to
selected invocation IDs. ``compiler.validation` checks
keyword-call compatibility and annotations against spec function contracts.
Generic loading and signature introspection remain in `uptimely.entrypoint`.
`Compiler.entrypoints` parses only selected invocations' locations, once per
distinct location. Invalid-location errors identify the entrypoint string.

`plan.invocations` retains declaration order. For sequential execution, use
`plan.execution_invocations`: this cached flat list follows stage order and
preserves ordering within each stage, avoiding nested loops in consumers.

<div class="api-reference" markdown="1">

## compiler

`uptimely.compiler.compiler` provides the compilation entry point.

::: uptimely.compiler.compiler
    options:
      heading_level: 3
      show_root_heading: false
      members: [Compiler]

## graph

`uptimely.compiler.graph` defines invocation nodes and organizes their
dependencies. A node's function kind comes from its function declaration in
the Spec rather than being stored on the node.

::: uptimely.compiler.graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [InvocationNode, InvocationGraph]

## execution_plan.models

`uptimely.execution_plan.models` defines the portable execution plan and its
invocations.

::: uptimely.execution_plan.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [Invocation, ExecutionPlan, PLAN_VERSION]

## execution_plan.serialization

`uptimely.execution_plan.serialization` reads and writes plan JSON.

::: uptimely.execution_plan.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members: [to_dict, from_dict, export_json, from_json]

</div>
