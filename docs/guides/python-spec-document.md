# Spec Python examples

Load or convert a Spec with [api](../python/spec-api.md), then pass it to the
[compiler](../python/compiler.md) to make an execution plan. The module-level helpers
are also available as `uptimely.spec.load_spec` and `uptimely.spec.from_python`.

## Loading and conversion

Loading and conversion validate the Spec by default. Compile it when you need
an execution plan.

Pass `validate=False` to `load_spec()` or `from_python()` to defer declaration
checks. Document structure and Python declaration checks still run. Do this
only when you will validate or compile the Spec before using it.

```python
# example

from uptimely import spec

document = spec.load_spec("spec.json")
```

## Validate a document

To run validation directly, defer validation while loading, then call
`validate_spec(document)`.

```python
# example

from uptimely import spec
from uptimely.spec.validation import validate_spec

document = spec.load_spec("spec.json", validate=False)
validate_spec(document)
```
