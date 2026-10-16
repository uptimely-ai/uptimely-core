# Python authoring

`uptimely.analytics.python` provides declarations that convert to the
[analytics document model](analytics/model.md). The sections below follow the
authoring modules in the source tree.

For a runnable example, see the
[analytics project structure](../../development/project-structure.md).

<div class="api-reference" markdown="1">

## analytics

`uptimely.analytics.python.analytics` groups declarations into a
`PythonAnalytics` definition.

::: uptimely.analytics.python.analytics
    options:
      heading_level: 3
      show_root_heading: false

## entity

`uptimely.analytics.python.entity` groups related datasets.

::: uptimely.analytics.python.entity
    options:
      heading_level: 3
      show_root_heading: false

## dataset

`uptimely.analytics.python.dataset` declares datasets and their features.

::: uptimely.analytics.python.dataset
    options:
      heading_level: 3
      show_root_heading: false

## dimension

`uptimely.analytics.python.dimension` declares shared dimensions.

::: uptimely.analytics.python.dimension
    options:
      heading_level: 3
      show_root_heading: false

## feature

`uptimely.analytics.python.feature` declares dataset features and calculations.

::: uptimely.analytics.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## mappings

`uptimely.analytics.python.mappings` declares relationships between datasets.
It is also exposed as `uptimely.analytics.mapping`.

::: uptimely.analytics.python.mappings
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.analytics.python.bind` binds function arguments to declared values.

::: uptimely.analytics.python.bind
    options:
      heading_level: 3
      show_root_heading: false

## ref

`uptimely.analytics.python.ref` builds references to functions and analytics
objects.

::: uptimely.analytics.python.ref
    options:
      heading_level: 3
      show_root_heading: false

## row_context

`uptimely.analytics.python.row_context` declares row windows for functions.
The runtime value is documented under [row context](row-context.md).

::: uptimely.analytics.python.row_context
    options:
      heading_level: 3
      show_root_heading: false

## conversion

`uptimely.analytics.python.conversion` converts declarations to document model
objects. Use [api.from_python](analytics/api.md#uptimely.analytics.api.from_python)
to convert and semantically validate in one operation.

::: uptimely.analytics.python.conversion
    options:
      heading_level: 3
      show_root_heading: false

</div>
