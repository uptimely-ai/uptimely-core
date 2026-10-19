# Spec models

`uptimely.spec.model` defines the spec document structure, independent
of its authoring format. The [spec format reference](../../../components/spec.md)
describes the document structure.

The compiler constructs executable invocations from these declarations.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.model.spec` defines the root spec document.

::: uptimely.spec.model.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [Spec, SUPPORTED_SPEC_VERSION]

## common

`uptimely.spec.model.common` defines shared dimensions, arguments, and
bindings.

::: uptimely.spec.model.common
    options:
      heading_level: 3
      show_root_heading: false
      members: [StrictModel, SpecSource, Dimension, Argument, BindingArgument, Binding]

## dataset

`uptimely.spec.model.dataset` defines entities, datasets, features, and
their relationships.

::: uptimely.spec.model.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [Entity, Dataset, Feature, Order, RowScope, Mapping, MappingFeatures]

## functions

`uptimely.spec.model.functions` defines reusable function metadata and the
function catalog.

::: uptimely.spec.model.functions
    options:
      heading_level: 3
      show_root_heading: false
      members: [FunctionTemplate, FunctionCatalog, FUNCTION_TYPES]

For supported operation types and values, see
[function contracts](../contracts.md).

</div>
