# Compiler and plans

`uptimely.compiler` turns a loaded Spec into a portable execution plan.
`uptimely.execution_plan` owns the neutral plan model and JSON serialization.
The compiler graph provides dependency and topology queries; presentation and
graph formatting are owned by Explorer.

Load a Spec with `uptimely.spec.load_spec` (or create one with
`uptimely.spec.from_python`), then compile it:

```python
from uptimely import compiler, spec

specification = spec.load_spec("spec.json")
plan = compiler.Compiler().compile(specification, features=["health_signal_normalized"])
```

Compilation validates the current Spec, so semantic changes made after loading
are checked before graph construction.
The phases are validation, graph construction and feature selection, scheduling,
portable invocation creation, implementation inspection, and plan assembly.

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
