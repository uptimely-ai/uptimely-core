# Spec validation

Spec loading and Python conversion validate declarations by default. To run
validation directly, call `validate_spec(document)`. Passing `validate=False`
to `load_spec()` or `from_python()` defers these checks; document shape and
field types are still checked.

Validation checks references, declarations, and dependency cycles. Errors are
reported as `ValueError`; structured errors use `SpecError`, which includes a
rule code and the location of the invalid declaration.

```python
from uptimely.spec.validation import validate_spec

validate_spec(document)
```

After editing a document, call `document.rebuild()` before validating or
compiling it so the checks use fresh declarations.

::: uptimely.spec.validation.spec
    options:
      heading_level: 2
      show_root_heading: false
      members: [validate_spec]

::: uptimely.spec.validation.errors
    options:
      heading_level: 2
      show_root_heading: false
      members: [SpecError]
