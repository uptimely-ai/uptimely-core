# Analytics models

`uptimely.analytics.model` defines the analytics document structure, independent
of its authoring format. The [analytics format reference](../../../components/analytics.md)
describes the document structure.

Derived functions and calls belong to [resolved](resolved.md), not these
document models.

<div class="api-reference" markdown="1">

## analytics

`uptimely.analytics.model.analytics` defines the root analytics document.

::: uptimely.analytics.model.analytics
    options:
      heading_level: 3
      show_root_heading: false
      members: [Analytics, SUPPORTED_ANALYTICS_VERSION]

## common

`uptimely.analytics.model.common` defines shared dimensions, arguments, and
bindings.

::: uptimely.analytics.model.common
    options:
      heading_level: 3
      show_root_heading: false
      members: [StrictModel, AnalyticsSource, Dimension, Argument, BindingArgument, Binding]

## dataset

`uptimely.analytics.model.dataset` defines entities, datasets, features, and
their relationships.

::: uptimely.analytics.model.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [Entity, Dataset, Feature, Order, RowScope, Mapping, MappingFeatures]

## functions

`uptimely.analytics.model.functions` defines reusable function metadata and the
function catalog.

::: uptimely.analytics.model.functions
    options:
      heading_level: 3
      show_root_heading: false
      members: [FunctionTemplate, FunctionCatalog, FUNCTION_TYPES]

For supported operation types and values, see
[function contracts](../contracts.md).

</div>
