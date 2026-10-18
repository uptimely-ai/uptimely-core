# Compiler and plans

`uptimely.compiler` turns spec into portable execution plans. Its `plan`
subpackage owns the plan models and JSON serialization.

<div class="api-reference" markdown="1">

## compiler

`uptimely.compiler.compiler` provides the compilation entry point.

::: uptimely.compiler.compiler
    options:
      heading_level: 3
      show_root_heading: false
      members: [Compiler]

## callable_node

`uptimely.compiler.callable_node` represents a callable in the compilation graph.

::: uptimely.compiler.callable_node
    options:
      heading_level: 3
      show_root_heading: false
      members: [CallableNode]

## execution_graph

`uptimely.compiler.execution_graph` organizes callable dependencies.

::: uptimely.compiler.execution_graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [CallableGraph]

## plan.models

`uptimely.compiler.plan.models` defines the portable plan and its callables.

::: uptimely.compiler.plan.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [Callable, Plan, ExecutionPlan, PLAN_VERSION]

## plan.serialization

`uptimely.compiler.plan.serialization` reads and writes plan JSON.

::: uptimely.compiler.plan.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members: [export_json, from_json]

</div>
