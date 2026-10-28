# Spec models

`uptimely.spec.model` defines the spec document structure, independent
of its authoring format. The [spec format reference](../../components/spec.md)
describes the document structure.

The compiler constructs executable invocations from these declarations.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.model.spec` defines the root spec document.

::: uptimely.spec.model.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [Spec, SPEC_VERSION]

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

`Entity.datasets` is a dictionary keyed by dataset ID. Access a dataset with
`document.entities["pump"].datasets["telemetry"]`, or iterate over
`entity.datasets.values()`. The internal `Dataset.id` is derived from the JSON
object key and excluded from serialized dataset attributes.

::: uptimely.spec.model.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [Entity, Dataset, Feature, Order, RowScope, Action, ActionFeatures]

## functions

`uptimely.spec.model.functions` defines reusable function metadata and the
function catalog.

::: uptimely.spec.model.functions
    options:
      heading_level: 3
      show_root_heading: false
      members: [FunctionTemplate, FunctionCatalog]

For supported function kinds and values, see the
[spec vocabulary](../spec-vocabulary.md).

</div>
