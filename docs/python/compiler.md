# Compiler and plans

`uptimely.compiler` creates an execution plan from a loaded Spec.
`uptimely.plan` reads and writes plans. An operator describes how a
function is used; the plan records that work for the engine to run.

Load a Spec with `uptimely.spec.load_spec` (or create one with
`uptimely.spec.from_python`), then compile it:

```python
from uptimely import compiler, plan as plan_io, spec

specification = spec.load_spec("spec.json")
compiled_plan = compiler.Compiler().compile(specification, features=["health_signal_normalized"])
plan_io.export_json(compiled_plan, "execution_plan.json")
```

Compilation checks the Spec before creating the plan. Use
`plan_io.export_json` to save it and `plan_io.from_json` to load
it. Plans from older versions are not supported; rebuild the bundle from its
source Spec after upgrading Uptimely.

An invocation represents one function call and retains the owning operator ID.
Fragment-producing operators have separate compute and merge invocations,
distinguished by their function kinds; consumers depend on publication after
merge. Only the compute invocation owns the operator's logical output features.
Invocation nodes carry their full output feature list, not a single feature ID.
The compiler resolves `$features.@` from an unambiguous declared output when
emitting binding arguments.
Dependencies come from declared interface inputs and outputs, plus the edge
from a fragment-producing compute invocation to its merge invocation.
One shared feature index uses the function kind's `produces_features` contract
and resolves each output to its merge invocation when present, otherwise compute.

Each invocation carries the runtime contract needed without consulting the Spec:
`id_columns` lists target keys, `column_types` maps typed target columns to logical
types, and `argument_types` maps declared argument names to their types. The
compiler takes key types from canonical dimension declarations, ahead of any
local feature metadata. These fields survive plan serialization. Saved plans
without them must be rebuilt; loading reports a recompile error rather than
running without key or type information.

Plans use strict Pydantic models to validate invocation fields and stage
relationships at construction and load time. They cache `invocations_by_id`
and `execution_stages`, along with resource views: `function_ids`, `profile_ids`,
`arguments` (invocation ID to bound arguments), `features` (output feature ID to
producing invocations), `calculated_features`, `entrypoints`, and
`invocations_by_kind`, and `count_per_kind` (invocation counts keyed and sorted by
function kind). Output features include dimension outputs; the Spec
remains the source of feature metadata. Repeated reads reuse the same cached
views. Each resource view is built independently, so using one does not eagerly
materialize unrelated indexes. Treat the views and their nested containers as
read-only. For changes, use `copy.replace`; it constructs a new validated plan
with fresh cached views.
Indexes do not change the portable JSON format.

Compiler responsibilities are separated by module. Each `compile()` call creates
a private compilation context that owns its graph, selected features, entrypoints,
signatures, and cached plan resources. A compiler instance retains no active build
state, so it can be reused for sequential, nested, or concurrent compilations.
Graph selection deduplicates identifiers in input order. The context validates
each enabled function once and parses only selected entrypoints. The
`compiler.validation` module checks keyword-call compatibility and annotations
against spec function contracts. Generic loading and signature introspection
remain in `uptimely.entrypoint`.

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
interface-derived dependencies.

::: uptimely.compiler.graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [InvocationNode, InvocationGraph]

## plan.models

`uptimely.plan.models` defines the portable execution plan and its
invocations.

::: uptimely.plan.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [Invocation, ExecutionPlan, PLAN_VERSION]

## plan.serialization

`uptimely.plan.serialization` reads and writes plan JSON.

::: uptimely.plan.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members: [to_dict, from_dict, export_json, from_json]

</div>
