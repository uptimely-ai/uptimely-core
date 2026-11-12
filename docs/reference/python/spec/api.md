# Spec operations

`uptimely.spec.api` provides functions to load a Spec or convert Python
declarations.

Loading and conversion validate the Spec by default. Compile it when you need
an execution plan.

Pass `validate=False` to `load_spec()` or `from_python()` to defer declaration
checks. Document structure and Python declaration checks still run. Do this
only when you will validate or compile the Spec before using it.

```python
from uptimely import compiler, spec

document = spec.load_spec("spec.json", validate=False)
plan = compiler.Compiler().compile(document)
```

<div class="api-reference" markdown="1">

## api

::: uptimely.spec.api
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - load_spec
        - from_python

</div>
