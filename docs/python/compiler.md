# Compiler and plans

`uptimely.compiler` turns a loaded Spec into a portable execution plan.
`uptimely.execution_plan` owns the neutral plan model and JSON serialization.
The compiler graph provides dependency and topology queries; presentation and
graph formatting are owned by Explorer.

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
dependencies.

::: uptimely.compiler.graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [InvocationNode, InvocationGraph]

## execution_plan.models

`uptimely.execution_plan.models` defines the portable execution plan and its
callables.

::: uptimely.execution_plan.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [Callable, ExecutionPlan, PLAN_VERSION]

## execution_plan.serialization

`uptimely.execution_plan.serialization` reads and writes plan JSON.

::: uptimely.execution_plan.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members: [to_dict, from_dict, export_json, from_json]

</div>
