# Execution engine

`uptimely.engine` executes [compiled plans](compiler.md). Configuration and
results are separate from the adapters used to access data, resources, and
Python callables.

<div class="api-reference" markdown="1">

## engine

`uptimely.engine.engine` provides the execution entry point.

::: uptimely.engine.engine
    options:
      heading_level: 3
      show_root_heading: false
      members: [Engine]

## config

`uptimely.engine.config` defines runtime settings.

::: uptimely.engine.config
    options:
      heading_level: 3
      show_root_heading: false
      members: [EngineConfig]

## result

`uptimely.engine.result` describes execution outputs.

::: uptimely.engine.result
    options:
      heading_level: 3
      show_root_heading: false
      members: [ExecutionResult]

## backend

`uptimely.engine.backend` defines adapter protocols and their built-in
implementations.

### Adapter protocols

Implement these interfaces to customize dataframe operations, resource
resolution, or callable loading.

::: uptimely.engine.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [DataFrameBackend, ResourceResolver, CallableLoader]

### Built-in adapters

The default implementations use Polars, plan resources, and Python entry points.

::: uptimely.engine.backend
    options:
      heading_level: 4
      show_root_heading: false
      members: [PolarsBackend, PlanResourceResolver, EntrypointLoader]

</div>
