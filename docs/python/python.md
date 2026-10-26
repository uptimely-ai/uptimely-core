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
    Dataset,
    Dimension,
    Entity,
    Feature,
    FunctionMapping,
    operation,
    ref,
)

pump_dimension = Dimension(id="pump", type="string")
assets = Entity(id="assets", name="Assets", dimensions=[pump_dimension])


@operation("collapse")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame: ...


class Pump(Dataset):
    id = "pump_summary"
    description = "Maximum bearing temperature per pump."
    entity = assets

    temperature_max = FunctionMapping(
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
    )
```

```python
from uptimely.spec.python import PythonSpec

python_spec = PythonSpec(
    datasets={assets: [Pump()]},
    name="Pump analytics",
)
```

`PythonSpec` groups datasets by entity and derives its entities, dimensions, and
function catalog. `Model([Pump]).to_declarations()` optionally registers dataset
classes.

`FunctionMapping` takes `function`, `arguments`, and `outputs`. Decorate callable
implementations with `@operation(...)`; use `ref.function(..., operation=...)`
for entrypoint strings. Implementations aren't called during authoring; assembly
checks callable parameter names and required arguments.
`read` functions take no dataframe arguments. `conform`, `collapse`, and
`expand` each take only their foreign/source dataframe; the engine supplies and
reconciles the target dataset separately.
The implementation module's package must be installed in the build and runtime
environments; install a local project package in editable mode for development.

In Python authoring, declare `inputs` explicitly whenever practical. If
`inputs` is omitted, feature references in `arguments` are used to infer them;
if `inputs` is supplied, it defines the dependencies instead. References such
as `ref.feature("result").id` pass an identifier, not feature data, and may be
used for output-name arguments. Declare produced features in `outputs`; they
are not inferred from arguments. In the resulting spec document, dependencies
are recorded explicitly in `features.inputs`. Writes use `outputs=[]`. For
generated declarations, use `Dataset(id=..., mappings={...})`.

### Migrating from list-based declarations

- Replace `features` and list-based `mappings` with named mappings. Put feature
  metadata in each mapping's `outputs`; use `Feature.name` for feature IDs.
- Replace `Mapping(bind=..., id=...)` with `FunctionMapping(function=...,
  arguments=..., outputs=...)`. The mapping attribute or dictionary key supplies
  its ID; `function_id` can override the catalog ID.
- Convert individual declarations with `Feature.to_model()` and
  `FunctionMapping.to_model(identifier)`.

The document model and exported JSON format are unchanged.

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
datasets with them through the `PythonSpec.datasets` mapping.
Conversion produces an ID-keyed dataset dictionary in the canonical model and
exported JSON, without repeating `id` in the JSON attributes. Duplicate dataset
IDs within an entity are rejected rather than overwritten.

::: uptimely.spec.python.entity
    options:
      heading_level: 3
      show_root_heading: false

## dataset

`uptimely.spec.python.dataset` declares dataset scope, named mappings, and optional
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

`uptimely.spec.python.feature` declares metadata for mapping outputs.

::: uptimely.spec.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## mappings

`uptimely.spec.python.mappings` declares analytical function bindings and outputs.
The module is also exposed as `uptimely.spec.python.mapping`.

::: uptimely.spec.python.mappings
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.spec.python.bind` provides lower-level nested argument bindings and
serialization helpers. Top-level mappings bind functions directly through their
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
    operation="vectorize",
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
