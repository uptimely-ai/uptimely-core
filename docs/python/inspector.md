# Binding inspector

The binding inspector compares a validated Spec with Python implementation
signatures before compilation.

It checks that implementations accept declared arguments as keywords, that
required parameters are declared, and that available argument and return
annotations agree with the function contract.

The build package uses this inspector before invoking the Compiler. The
inspector is independent of plan compilation and can inspect a Spec and return
portable signature metadata for use by callers.

::: uptimely.inspector.bindings
    options:
      heading_level: 2
      show_root_heading: false
      members: [BindingInspection]
