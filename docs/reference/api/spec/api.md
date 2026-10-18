# Spec operations

`uptimely.spec.api` provides the application-level operations for loading,
converting, and preparing spec.

Loading and Python conversion perform semantic validation. Preparation resolves
functions and calls without adding derived state to the
[spec document](model.md).

<div class="api-reference" markdown="1">

## api

::: uptimely.spec.api
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - load_spec
        - from_python
        - prepare_spec

</div>
