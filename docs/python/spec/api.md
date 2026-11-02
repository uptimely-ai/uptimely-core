# Spec operations

`uptimely.spec.api` provides the application-level operations for loading,
and converting spec.

Loading and Python conversion perform semantic validation directly on the
[spec document](model.md). They do not create executable invocations or attach
derived state. Compile the document when an execution plan is needed.

Both `load_spec(..., validate=False)` and `from_python(..., validate=False)`
defer semantic validation. Document structure and Python declaration checks
still run. Validation is enabled by default; only defer it when a later step,
such as `Compiler.compile()`, validates the document before using it.

`load_spec(..., log_structure=False)` suppresses structural validation debug
messages without disabling any checks. Builds use this for saved-bundle rereads,
so only the original source load emits the document-structure summary.

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
