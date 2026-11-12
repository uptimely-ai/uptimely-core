# Spec models

`uptimely.spec.model` defines the document created from Python declarations or
loaded from JSON. Use [`uptimely.spec`](../spec.md) to load, convert, validate,
and write documents.

The main models are `Spec`, `Profile`, `Dimension`, `Resolution`, `Feature`,
`Operator`, `Interface`, and `Binding`. A profile's `grain` identifies its rows.
Features describe calculated values, while operators describe the functions and
arguments used to produce them.

## Looking up declarations

Use the document's `profiles`, `features`, and `operators` views to find
declarations. `profile.identifiers(...)` returns the keys selected by its grain.
Use `profile.relations` for declared links to other profiles. The document also
provides views for feature owners, producers, and operator-to-profile
relationships.

These views refer to the document's declarations. Treat the document and its
views as read-only after loading or compiling it. If you edit a model, call
`document.rebuild()` and validate or compile the returned document.

::: uptimely.spec.model.spec
    options:
      heading_level: 2
      show_root_heading: false
      members: [Spec]

::: uptimely.spec.model.dimension
    options:
      heading_level: 2
      show_root_heading: false
      members: [Dimension, Resolution]

::: uptimely.spec.model.profile
    options:
      heading_level: 2
      show_root_heading: false
      members: [Profile, Feature, Operator, Interface, Order]

::: uptimely.spec.model.binding
    options:
      heading_level: 2
      show_root_heading: false
      members: [Binding]

::: uptimely.spec.model.functions
    options:
      heading_level: 2
      show_root_heading: false
      members: [Argument, FunctionTemplate]
