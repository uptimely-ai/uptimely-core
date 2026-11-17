# Spec vocabulary

These modules provide shared types used when describing and checking a Spec.
Most projects use the Python helpers in [Python authoring](../guides/python-authoring.md) instead.

## Operator bindings

`OPERATOR_BINDINGS` describes the required `compute` binding and the optional
`merge` binding. Dataframe counts are independent of logical feature dependencies.

::: uptimely.spec.operator_bindings
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - BindingContract
        - BindingKind
        - PrimaryBindingKind
        - OPERATOR_BINDINGS
