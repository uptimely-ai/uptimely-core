# Python authoring

`uptimely.spec.python` provides declarations that convert to the
[spec document model](spec/model.md). The sections below follow the
authoring modules in the source tree.

For a runnable example, see the
[analytics project structure](../project-layout/project-structure.md).

## Declarative datasets

```python
import polars as pl

from uptimely.spec.python import (
    Action,
    Dataset,
    Dimension,
    Entity,
    Feature,
    function,
    ref,
)

pump_dimension = Dimension(id="pump", type="string")
assets = Entity(id="assets", name="Assets", dimensions=[pump_dimension])


@function(kind="collapse")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame: ...


class Pump(Dataset):
    id = "pump_summary"
    description = "Maximum bearing temperature per pump."
    entity = assets

    producers = [
        Action(
            id="temperature_max",
            function=maximum,
            arguments=dict(
                dataset=ref.dataset("telemetry").dataframe,
                feature=ref.feature("bearing_temperature"),
                dimensions=["pump"],
                output=ref.feature("bearing_temperature_max").id,
            ),
            outputs=[
                Feature(
                    name="bearing_temperature_max",
                    type="float",
                    unit="C",
                    description="Maximum observed bearing temperature.",
                ),
            ],
        ),
    ]
```

```python
from uptimely.spec.python import PythonSpec

python_spec = PythonSpec(
    dimensions=[pump_dimension],
    entities=[assets],
    datasets=[Pump],
    name="Pump analytics",
)
```

`PythonSpec` requires explicit `dimensions`, `entities`, and `datasets` sequences,
including empty sequences when appropriate. It instantiates dataset classes and
groups datasets using their `entity` attribute, which accepts an entity ID string
or an `Entity` object. An entity's `dimensions` accepts dimension ID strings,
`Dimension` objects, or a mixture of both. Referenced entities and dimensions
must also appear in the corresponding `PythonSpec` sequence; object references
do not register them implicitly. Duplicate registrations, undeclared references,
and conflicting object metadata are rejected.

The explicit dataset sequence is authoritative; datasets nested in an `Entity`
are not automatically registered. Unused registered entities and dimensions are
preserved. Reference resolution does not mutate the supplied declarations.
The function catalog is collected from the registered datasets.
Convert declarations containing ID references through `PythonSpec.to_model()`
or `PythonSpec.to_dict()` so those references can be resolved.
`Model([Pump]).to_declarations()` optionally registers dataset classes.

`Action` declares work without executing it. It takes `id`, `function`,
`arguments`, and `outputs`, with optional `inputs`, `function_id`, and
`row_context` requirements. Optionally annotate callable implementations with
`@function(kind=...)`. The decorator attaches semantic metadata for validation;
it returns the original function without wrapping or executing it. Alternatively,
keep implementations undecorated and supply their contract through
`ref.function(implementation, kind=...)`. Entrypoint strings also use explicit
function references. Kind belongs to the function, not the action.

An explicit reference kind must agree with decorated metadata. References to
decorated callables inherit their kind when it is omitted. Decoration is
optional, but a function kind is still required to build an executable action;
Uptimely never guesses a producer's kind from its signature or collection.
Implementations aren't called during authoring; assembly checks callable
parameter names and required arguments.

```python
from uptimely.spec.python import function, ref


@function(kind="collapse")
def maximum(dataset, feature, dimensions, output): ...


decorated = ref.function(maximum)  # Carries the declared collapse contract.
external = ref.function("third_party.analytics:maximum", kind="collapse")
```
`read` functions take no dataframe arguments. `conform`, `collapse`, and
`expand` each take only their foreign/source dataframe; the engine supplies and
reconciles the target dataset separately. `conform` sources and targets have
the same dimensions, `collapse` sources have a strict superset of the target
dimensions, and `expand` sources have a strict subset.
Declare dimensional matching keys explicitly with
`ref.current_dataset().dimensions.ids` (or a dataset-specific
`.dimensions.ids` selector where appropriate). Grouping and ordering
references do not implicitly select matching keys. Data-producing functions
return Polars `DataFrame` or `LazyFrame` fragments; other dataframe types and
custom adapters are not currently supported. The engine assembles fragments
for the same dataset by complete keys with a full outer join, preserving
partial coverage while rejecting duplicate keys and feature collisions. See
the runnable
[dimensional operations example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/dimensional_operations)
and [engine fragment contract](../components/engine.md#fragments).
The implementation module's package must be installed in the build and runtime
environments; install a local project package in editable mode for development.

In Python authoring, declare `inputs` explicitly whenever practical. If
`inputs` is omitted, feature references in `arguments` are used to infer them;
if `inputs` is supplied, it defines the dependencies instead. References such
as `ref.feature("result").id` pass an identifier, not feature data, and may be
used for output-name arguments. Declare produced features in `outputs`; they
are not inferred from arguments. In the resulting spec document, dependencies
are recorded explicitly in `features.inputs`. Writes use `outputs=[]`. For
generated declarations, use `Dataset(id=..., producers=[...], publishers=[...],
pipelines=[...])`.

### Dataset action collections

Each dataset exposes three lists of actions:

| Collection | Allowed kinds | Purpose |
| --- | --- | --- |
| `producers` | `read`, `collapse`, `conform`, `expand`, `vectorize` | Produce dataset features. |
| `publishers` | `write` | Write dataset results to external destinations. |
| `pipelines` | `escape` | Invoke opaque custom processing with declared dependencies and outputs. |

Kinds remain explicit on functions or function references. Putting an action in
the wrong collection raises an error; placement never changes its kind.
Action IDs must be non-empty and unique across all three collections. Reusing
one function in multiple actions is allowed with distinct action IDs;
`function_id` separately identifies its reusable catalog contract.

Collections default to empty and are copied for each dataset instance.
Constructor arguments replace the corresponding class collections, including
when an empty list is passed. Subclasses inherit collections using normal Python
attribute lookup: defining `producers` replaces the inherited list rather than
merging it. To extend it, write `producers = [*Base.producers, another_action]`.

List order does not impose execution order, nor do collections define execution
phases. Declared feature dependencies determine scheduling, including
dependencies between producers and pipelines. Uptimely does not inspect a
pipeline function's internal steps.

### Migrating from FunctionMapping

- Replace `FunctionMapping(...)` with `Action(id=..., ...)`. Move named dataset
  attributes or entries in `mappings={...}` into the appropriate action list.
  Use the former attribute name or dictionary key as the action ID.
- Replace imports from `uptimely.spec.python.mapping` or
  `uptimely.spec.python.mappings` with `uptimely.spec.python.actions`, or import
  `Action` directly from `uptimely.spec.python`.
- Access declarations through their collection rather than `Dataset.mappings`.
- Convert an action with `Action.to_model()`; its own ID supplies the canonical
  action identifier. Feature metadata remains in `outputs`, and
  `Feature.to_model()` is unchanged.

The old Python authoring names and `mappings` constructor argument are removed.
The canonical document model and exported JSON now use `actions` in each
dataset. This breaking document change is spec version 3.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.python.spec` groups declarations into a
`PythonSpec` definition.

::: uptimely.spec.python.spec
    options:
      heading_level: 3
      show_root_heading: false

## entity

`uptimely.spec.python.entity` declares entity metadata and dimensions.

Python entity declarations describe their dimensions and metadata. Associate
datasets with them by setting the `entity` class attribute on each dataset.
Conversion produces an ID-keyed dataset dictionary in the canonical model and
exported JSON, without repeating `id` in the JSON attributes. Duplicate dataset
IDs within an entity are rejected rather than overwritten.

::: uptimely.spec.python.entity
    options:
      heading_level: 3
      show_root_heading: false

## dataset

`uptimely.spec.python.dataset` declares dataset scope, action collections, and optional
class registries.

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

`uptimely.spec.python.feature` declares metadata for action outputs.

::: uptimely.spec.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## actions

`uptimely.spec.python.actions` declares analytical work, function arguments,
feature inputs and outputs, and execution requirements.

::: uptimely.spec.python.actions
    options:
      heading_level: 3
      show_root_heading: false

## functions

`uptimely.spec.python.functions` defines optional implementation-level semantics.
Import `function` directly from `uptimely.spec.python` for
`@function(kind="...")`, or import the `functions` module for
`@functions.function(kind="...")`. The former `@kind(...)` decorator is removed.
The decorator does not prove implementation behavior; it declares the contract
that Uptimely validates at its supported boundaries.

::: uptimely.spec.python.functions
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.spec.python.bind` provides lower-level nested argument bindings and
serialization helpers. Actions bind functions directly through their
`function` and `arguments` attributes.

::: uptimely.spec.python.bind
    options:
      heading_level: 3
      show_root_heading: false

## ref

`uptimely.spec.python.ref` builds references to functions and spec
objects.

Function references accept `validate_signature`, defaulting to `True`.
Conversion preserves it in the function catalog and exported JSON. When
`False`, compilation and documentation do not import the implementation or
inspect its signature. Spec-level contracts and declared feature dependencies
are still validated, and execution still requires a loadable implementation.

Use an entrypoint string when the implementation must not be imported while
loading the Python spec:

```python
ref.function(
    "other_project.functions:calculate",
    kind="vectorize",
    validate_signature=False,
)
```

Python spec declarations execute during source loading. Do not import an
unavailable analytical implementation from the declaration module itself;
pass its entrypoint as a string instead.

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
