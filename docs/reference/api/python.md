# Python authoring

`uptimely.spec.python` provides declarations that convert to the
[spec document model](spec/model.md). The sections below follow the
authoring modules in the source tree.

For a runnable example, see the
[analytics project structure](../../development/project-structure.md).

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.python.spec` groups declarations into a
`PythonSpec` definition.

::: uptimely.spec.python.spec
    options:
      heading_level: 3
      show_root_heading: false

## entity

`uptimely.spec.python.entity` groups related datasets.

::: uptimely.spec.python.entity
    options:
      heading_level: 3
      show_root_heading: false

## dataset

`uptimely.spec.python.dataset` declares datasets and their features.

::: uptimely.spec.python.dataset
    options:
      heading_level: 3
      show_root_heading: false

## dimension

`uptimely.spec.python.dimension` declares shared dimensions.

::: uptimely.spec.python.dimension
    options:
      heading_level: 3
      show_root_heading: false

## feature

`uptimely.spec.python.feature` declares dataset features and calculations.

::: uptimely.spec.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## mappings

`uptimely.spec.python.mappings` declares relationships between datasets.
It is also exposed as `uptimely.spec.mapping`.

::: uptimely.spec.python.mappings
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.spec.python.bind` binds function arguments to declared values.

::: uptimely.spec.python.bind
    options:
      heading_level: 3
      show_root_heading: false

## ref

`uptimely.spec.python.ref` builds references to functions and spec
objects.

::: uptimely.spec.python.ref
    options:
      heading_level: 3
      show_root_heading: false

## row_context

`uptimely.spec.python.row_context` declares row windows for functions.
The runtime value is documented under [row context](row-context.md).

::: uptimely.spec.python.row_context
    options:
      heading_level: 3
      show_root_heading: false

## conversion

`uptimely.spec.python.conversion` converts declarations to document model
objects. Use [api.from_python](spec/api.md#uptimely.spec.api.from_python)
to convert and semantically validate in one operation.

::: uptimely.spec.python.conversion
    options:
      heading_level: 3
      show_root_heading: false

</div>
