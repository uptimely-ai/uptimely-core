# Spec validation

Validation checks references, declarations, and dependency cycles. Errors are
reported as `ValueError`; structured errors use `SpecError`, which includes a
rule code and the location of the invalid declaration.

Spec validation is independent of implementation loading and binding
implementation details. Use
[Binding inspector](inspector.md) to compare declarations with Python
implementation signatures.

After editing a document, call `document.rebuild()` before validating or
compiling it so the checks use fresh declarations.

For validation examples, see
[Work with Spec documents](../guides/python-spec-document.md#validate-a-document).

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
