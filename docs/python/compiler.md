# Compiler and plans

`uptimely.compiler` creates an execution plan from a loaded Spec.
`uptimely.execution_plan` reads and writes plans. A mapping describes how a
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
dependencies. A node's operation kind comes from its function declaration in
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
