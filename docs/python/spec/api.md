# Spec operations

`uptimely.spec.api` provides the application-level operations for loading,
and converting spec.

Loading and Python conversion perform semantic validation directly on the
[spec document](model.md). They do not create executable invocations or attach
derived state. Compile the document when an execution plan is needed.

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
