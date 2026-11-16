# Compiler and plans

The compiler turns a loaded Spec into an execution plan. The engine runs that
plan. Use [`Uptimely`](../../reference/python/application.md) to build the complete project bundle.

```python
from uptimely import Compiler, spec
from uptimely import plan as plan_io

document = spec.load_spec("spec.json")
execution_plan = Compiler().compile(
    document,
    features=["health_signal_normalized"],
)
plan_io.export_json(execution_plan, "execution_plan.json")
```

Compilation validates the Spec and checks that referenced Python functions can
be called with the declared arguments. Rebuild the project after changing the
Spec. Plans saved by older Uptimely versions are not supported; rebuild them
from the Spec.
