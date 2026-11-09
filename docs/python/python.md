# Python authoring

Use `import uptimely as up` for Python authoring declarations and `up.ref` for
deferred references. These declarations convert to the
[spec document model](spec/model.md). Their defining modules remain available
under `uptimely.spec.python`; the reference sections below follow those modules.

For a runnable example, see the
[analytics project structure](../project-layout/project-structure.md).

## Build-time declarations and runtime configuration

Python declarations define the build-time workflow. Operators, bindings, and
profile grain are compiled into the plan, so changes to them require a rebuild.
Runtime parameters, source/sink locations, and validation controls normally
change execution without changing the graph.

| Setting | Ownership | Rebuild required? |
| --- | --- | --- |
| Operators, bindings, and profile grain | Build-time declarations | Yes |
| Runtime parameters, source/sink locations, and validation controls | Project/runtime configuration and run options | Normally no |

Runtime parameters can change calculation results without changing the plan.
The plan's required backend is fixed at build time; an incompatible backend
setting fails rather than reinterpreting the plan.

## Declarative profiles

```python
import polars as pl
import uptimely as up
from uptimely.spec import feature_types

machine = up.Dimension(
    id="machine",
    resolutions=[up.Resolution(id="machine", key="machine", type="string")],
)


@up.function(returns="dataframe")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame: ...


class PumpFeatures(up.FeatureSet):
    bearing_temperature_max = up.Feature(
        type=feature_types.FLOAT,
        unit="C",
        description="Maximum observed bearing temperature.",
    )


class Pump(up.Profile):
    id = "pump_summary"
    name = "Pump Summary"
    description = "Maximum bearing temperature per pump."
    grain = [machine.resolution("machine")]
    features = PumpFeatures()

    assembly = [
        up.Operator(
            id="temperature_max",
            interface=up.Interface(
                outputs=[features.bearing_temperature_max],
            ),
            compute=up.Binding(
                function=maximum,
                arguments=dict(
                    dataset=up.ref.dataset("telemetry"),
                    feature=up.ref.feature("bearing_temperature"),
                    dimensions=up.ref.profile().grain.ids,
                    output=up.ref.feature("bearing_temperature_max"),
                ),
            ),
        ),
    ]
```

`Feature.id` is the stable feature identifier used by references and serialized
keys. `Feature.name` is an optional display label; when omitted, it is generated
by humanizing the ID (for example, `bearing_temperature_max` becomes
`Bearing Temperature Max`). Within a `FeatureSet`, the attribute name is used
as the ID when `id` is omitted; an explicit ID can be supplied when it should
differ from the attribute name. A `FeatureSet` subclass groups a profile's
feature declarations as attributes, which operators reference in their outputs
instead of repeating metadata inline. Logical feature types are available as
constants in `uptimely.spec.feature_types` and remain strings in the spec.

```python
python_spec = up.Spec(
    profiles=[Pump],
    name="Pump analytics",
)
```

Root-level `Spec`, `Profile`, `Operator`, `Interface`, `Binding`,
`Dimension`, `Resolution`, `Feature` and `FeatureSet` are Python
authoring classes.
Document-model classes remain under `uptimely.spec.model` and the existing
`uptimely.spec` exports. The authoring `Spec` is defined as
`uptimely.spec.python.spec.Spec` and exported as `up.Spec` and
`uptimely.spec.python.Spec`.

Dimensions have stable IDs and declare one or more keyed resolutions. A profile's
`grain` is a list of selected resolutions, one per dimension; select them with
`dimension.resolution("resolution_id")`. The selected resolution's key is the
dataframe column used by that profile. Optional dimension names are
human-readable labels generated from IDs when omitted.

Profile instances expose `profile.keys` and `profile.key_types`: all resolution
key columns for the dimensions used by their grain, and their logical types.
These include unselected resolutions without changing the grain or declaring
additional features. Dimensionless profiles return an empty list and dictionary.

`up.Spec` accepts the profile declarations only. It infers dimension and
resolution definitions from each profile's grain, requires repeated declarations
to agree, rejects unresolved resolutions and conflicting metadata, and emits
deterministic output. A profile's missing ID is inferred from its name, and a
missing name is humanized from its ID. If both are omitted, the profile class
name supplies the snake-case ID and humanized name. Profile IDs are globally
unique. The function catalog is collected from the registered profiles;
reference resolution does not mutate the supplied declarations.
`ProfileRegistry([Pump]).to_declarations()` can instantiate and register
profile classes.

`Operator` declares work without executing it. Its declaration fields are
ordered `id`, `interface`, optional `row_context`, `compute`, and optional
`merge`. `Binding` contains the implementation `function` and named
`arguments`; `Interface` contains feature `inputs` and `outputs`.
Interface inputs are optional: if omitted, feature references in compute
and optional merge arguments are inferred as dependencies, excluding declared
outputs and retaining first-occurrence order. If supplied, they define the
dependencies instead; an empty input list disables inference. `Interface`
validates feature references and rejects repeated input or output IDs when
constructed. It checks them again during conversion, so later mutations of its
collections cannot bypass those checks.

`Binding` owns a function reference and its reusable contract metadata,
callable argument validation (`bound_arguments()`), and conversion (`to_model()` and
`to_function_template()`). `Interface.to_model(compute=..., merge=...)` accepts
canonical bindings and builds feature selectors. `Operator` coordinates these
conversions and validates compute/merge compatibility; its existing metadata
properties and `bound_arguments()` delegate to the compute binding.
Entrypoint strings and function references are not imported during these
conversions; their signature checks are deferred until compilation.

`Operator` accepts an optional `row_context` requirement. The compute binding
can refer to its scalar attributes with `ref.row_context("before")`,
`ref.row_context("after")`, or `ref.row_context("dimension")`. Its function
catalog ID is derived from the referenced function name. Optionally annotate
callable implementations with `@function(returns=...)`.
The decorator attaches reusable argument and return contracts;
an optional `category="..."` may also be supplied as descriptive Spec metadata.
The category is unrestricted text and does not affect execution or validation.
The decorator returns the original function without wrapping or executing it. Alternatively,
keep implementations undecorated and supply their contract through
`ref.function(implementation, returns=...)`. Entrypoint strings also use explicit
function references. Operator meaning comes from its binding position and
source/target declarations, not from metadata attached to the implementation.

An explicit reference contract must agree with decorated metadata. Decoration
is optional: dataframe and `None` return annotations can establish the return
contract. Missing, opaque, or mixed annotations require explicit `returns`.
String references always require it because authoring does not import them.
Implementations aren't called during authoring; assembly checks callable
parameter names and required arguments.

```python
from uptimely.spec.python import function, ref


@function(returns="dataframe", category="aggregation")
def maximum(dataset, feature, dimensions, output): ...


decorated = ref.function(maximum)
external = ref.function("third_party.analytics:maximum", returns="dataframe")
categorized = ref.function(
    "third_party.analytics:maximum", returns="dataframe", category="aggregation"
)
```
Compute bindings take zero or one dataframe argument and declare `returns` as
`dataframe`, `none`, or `any` (an ignored result with logical dependencies).
Merge bindings take exactly two dataframe arguments and return a dataframe.
These roles belong to binding positions, not permanently to callables.
Derived `conform` sources and targets have
the same grain. `collapse` moves to a coarser grain, and `expand` moves to a
finer grain; parent links between resolutions describe valid coarsening and
refinement.
Declare dimensional matching keys explicitly with
`ref.profile().grain.ids` (or a named profile's `.grain.ids` selector).
Grouping and ordering references do not implicitly select matching keys.
With a merge binding, compute returns a Polars `DataFrame` or `LazyFrame`
fragment. Select the builtin merge explicitly with `merge=up.default_merge()`;
omitting a merge publishes a complete target rather than silently joining.
The builtin merge assembles fragments
for the same profile by complete keys with a full outer join, preserving
partial coverage while rejecting duplicate keys and feature collisions. An
`expand` fragment may omit dimension keys its lower-dimensional source cannot
supply; the engine left-joins such a fragment onto the accumulated profile frame by
the keys it carries, broadcasting a dimensionless fragment to every
observation. See the runnable
[dimensional operations example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/dimensional_operations)
and [engine fragment contract](../components/engine.md#fragments).

`vectorize` functions instead receive the accumulated target dataframe and
return that complete dataframe enriched with their declared outputs. They must
preserve existing columns and values, row count, key identities, and row order;
they do not return fragments and cannot declare a merge binding. The engine
always checks the returned schema, while opt-in runtime validation checks
preservation of existing values and row order. Functions must not mutate their
input dataframes: publishing by assignment cannot roll back mutations made by
user code.

Operators stage fragments only when they declare a `merge` binding.
Use `up.default_merge()` for the builtin grain merge, or provide a custom binding.
Changing an operator's merge binding requires rebuilding the project.
The implementation module's package must be installed in the build and runtime
environments; install a local project package in editable mode for development.

References such as `ref.feature("result").id` pass an identifier, not feature
data, and may be used for output-name arguments. Declare produced features in
`interface.outputs`; they are not inferred from arguments. In the resulting
spec document, dependencies are recorded explicitly in `interface.inputs`.
Writes use `interface=Interface(outputs=[])`. For
generated declarations, use `Profile(id=..., grain=[...], assembly=[...])`.

### Profile assembly

Each profile declares its work in one `assembly` list. For readability, a
mapping of group names to operator lists is also accepted and flattened in
insertion order:

```python
assembly = {
    "ingestion": [read_operator],
    "calculations": [calculate_operator],
    "publishing": [write_operator],
}
```

Groups are organizational only; execution roles come from compute and merge
binding positions. Operator IDs must be
non-empty and unique within the profile. Reusing one function in multiple
operators is allowed with distinct operator IDs; its function name identifies
the reusable catalog contract.

The assembly defaults to an empty list and is copied for each profile instance.
Constructor arguments replace the class declaration, including when an empty
list is passed. Subclasses inherit assembly using normal Python attribute lookup:
defining `assembly` replaces the inherited list rather than merging it. To extend
it, write `assembly = [*Base.assembly, another_operator]`.

List order and group order do not impose execution order. Declared feature
dependencies determine scheduling. Uptimely does not inspect an escape
function's internal steps.

### Migrating from FunctionMapping

- Replace `FunctionMapping(...)` with `Operator(id=..., ...)`. Move named profile
  attributes or entries in `mappings={...}` into the appropriate assembly list.
  Use the former attribute name or dictionary key as the operator ID.
- Replace imports from `uptimely.spec.python.mapping` or
  `uptimely.spec.python.mappings` with `uptimely.spec.python.assembly`, or import
  `Operator` directly from `uptimely.spec.python`.
- Access declarations through `Profile.assembly` rather than `Profile.mappings`.
- Convert an operator with `Operator.to_model()`; its own ID supplies the canonical
  operator identifier. Feature metadata remains in `outputs`, and
  `Feature.to_model()` is unchanged.

Python profiles expose declarations through `Profile.assembly`; canonical
documents and exported JSON use the same `assembly` key.
The current JSON contract is spec version 8. JSON profiles use an `assembly`
mapping whose operators declare `compute`, optionally `merge`, and `interface`;
see the [binding contracts](../components/spec.md#binding-roles-and-derived-operator-labels).

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.python.spec` groups declarations into a
`up.Spec` definition.

::: uptimely.spec.python.spec
    options:
      heading_level: 3
      show_root_heading: false

## profile

`uptimely.spec.python.profile` declares profile grain, metadata, assembly, and
optional class registries.

::: uptimely.spec.python.profile
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

`uptimely.spec.python.feature` declares metadata for operator outputs.

::: uptimely.spec.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## assembly module

`uptimely.spec.python.assembly` defines `Operator`, `Interface`, and `Binding`,
the declarations used in a profile's assembly.

::: uptimely.spec.python.assembly
    options:
      heading_level: 3
      show_root_heading: false

## functions

`uptimely.spec.python.functions` defines reusable callable contracts.
Import `function` directly from `uptimely.spec.python` for
`@function(returns="dataframe")`, or import the `functions` module for
`@functions.function(returns="dataframe")`. The `kind` argument is removed.
The decorator does not prove implementation behavior; it declares the contract
that Uptimely validates at its supported boundaries.

::: uptimely.spec.python.functions
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.spec.python.bind` provides lower-level nested argument bindings and
serialization helpers. Operators bind functions directly through their
`function` and `arguments` attributes.

::: uptimely.spec.python.bind
    options:
      heading_level: 3
      show_root_heading: false

## ref

`up.ref` (also available as `uptimely.spec.python.ref`) builds deferred
references to functions and spec objects. It does not construct or load data.

| Helper | Meaning |
| --- | --- |
| `up.ref.dataset()` | Current profile's dataframe. |
| `up.ref.dataset("telemetry")` | Named profile's dataframe. |
| `up.ref.fragment()` | Staged fragment for the current operator's merge binding. |
| `up.ref.feature("temperature")` | Input feature column; infers a dependency unless `inputs` is explicit. |
| `up.ref.feature("maximum")` | Identifier of a feature in the containing operator's `outputs`; no input dependency. |

`ref.feature()` does not declare a feature. An undeclared output name raises
`ValueError`, including references nested in lists, dictionaries, and bindings.
Use `ref.profile().dataset`, `ref.profile(name).dataset`,
`ref.feature(name)`, and `ref.feature(name).id` to create deferred references.
The general `.id` selector does not require the feature to be an operator output.

Function references accept `validate_signature`, defaulting to `True`.
Conversion preserves it in the function catalog and exported JSON. When
`False`, compilation and documentation do not import the implementation or
inspect its signature. Spec-level contracts and declared feature dependencies
are still validated, and execution still requires a loadable implementation.
When enabled, compilation checks keyword-call compatibility, required
parameters, positional-only parameters, and supported annotation contradictions.
Annotations may be omitted when `returns` is explicit; incompatible return
annotations are rejected when inspection is enabled. Disabling inspection
requires explicit `args` and `returns`; it does not disable binding-name or
dataframe-arity checks.

Function references also carry a `description` into the function catalog and
exported JSON. When a callable is referenced, the description defaults to the
summary line of its docstring; pass `description=` to override it. Entrypoint
strings have no default because the implementation is not imported while
loading the spec.

Use an entrypoint string when the implementation must not be imported while
loading the Python spec:

```python
ref.function(
    "other_project.functions:calculate",
    returns="dataframe",
    args={"dataset": "dataframe", "feature": "string"},
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
