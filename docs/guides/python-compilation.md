# Compile and serialize a plan {#compiler-and-plans}

The compiler turns a loaded Spec into an execution plan. The engine runs that
plan. Use [`Uptimely`](../python/application.md) to build the complete project bundle.

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

See [Spec validation](../python/spec-validation.md#spec-validation)
for declaration and implementation checks, and
[Execution plan versioning](../artifacts/execution-plan.md#versioning)
for compatibility and rebuild requirements.
