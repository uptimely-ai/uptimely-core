# Uptimely Core

Uptimely Core helps industrial teams build and run batch analytics with complex
feature dependencies.

Use it for machine telemetry, process analytics, failure prediction, and
factory optimization. Streaming abstractions are on the roadmap.

Definitions can be authored in Python and exported to JSON, or supplied directly as JSON. The built-in execution backend uses Polars, and the engine supports configurable runtime adapters.

> [!WARNING]
> This project follows semantic versioning, but is still at `0.x`: minor
> releases may include breaking changes. See the [changelog](https://github.com/uptimely-ai/uptimely-core/blob/main/CHANGELOG.md)
> for details.

## Demo

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-demo.gif)

Read more at [uptimely.ai website](https://uptimely.ai).

## Install

Python 3.13 or newer is required.

With pip:

```sh
pip install uptimely-core
```

With poetry:

```sh
poetry add uptimely-core
```

## End-to-end example

This short workflow downloads, builds, and runs the included pump analytics
project. The build compiles its analytics definition into an execution plan.
The run executes that plan.

With Poetry, prefix these commands with `poetry run`.

Download the example project:

```sh
uptimely examples
```

Build and run it:

```sh
uptimely build examples/pump_analytics --verbose
uptimely run examples/pump_analytics
```

The build creates files
under `examples/pump_analytics/_generated/build/`. Rebuild after changing the
project source.

## Python API

Author a spec in Python by describing its entity, dataset, and function
mappings. This small example reads two rows and defines a derived feature:

```python
import polars as pl

from uptimely.spec.python import (
    Dataset,
    Dimension,
    Entity,
    Feature,
    FunctionMapping,
    PythonSpec,
    operation,
    ref,
)

identifier = Dimension(id="id", type="integer")
measurements = Entity(
    id="measurements",
    name="Measurements",
    dimensions=[identifier],
)


@operation("read")
def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


@operation("vectorize")
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


dataset = Dataset(
    id="measurements",
    entity=measurements,
    mappings={
        "read": FunctionMapping(
            function=read_values,
            arguments={},
            outputs=[Feature(name="value")],
        ),
        "double": FunctionMapping(
            function=double,
            arguments={
                "dataset": ref.current_dataset().dataframe,
                "value": ref.feature("value"),
                "output": "doubled",
            },
            outputs=[Feature(name="doubled")],
        ),
    },
)

definition = PythonSpec(
    datasets={measurements: [dataset]},
    name="Measurements",
)
specification = definition.to_model()
```

## Further exploration

Use the project explorer to inspect a project visually:

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.

See the [documentation site](https://uptimely-ai.github.io/uptimely-core/) for
the full guides, and the [Python API reference](python/index.md) for
public classes, functions, and signatures.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`docs/`](index.md) | Architecture, specification, and development documentation. |
| [`examples/`](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/README.md) | Runnable examples and generated artifacts. |
| [`scripts/`](https://github.com/uptimely-ai/uptimely-core/tree/main/scripts) | Code snippets for repository management |
| [`src/uptimely/`](https://github.com/uptimely-ai/uptimely-core/tree/main/src/uptimely) | Package implementation for analytics, compilation, dependencies, documentation, and execution. |
| [`tests/`](https://github.com/uptimely-ai/uptimely-core/tree/main/tests) | Automated tests for the package and examples. |

## Development

See
[CONTRIBUTING.md](https://github.com/uptimely-ai/uptimely-core/blob/main/CONTRIBUTING.md) for the full workflow.

## License

Released under the [MIT license](https://github.com/uptimely-ai/uptimely-core/blob/main/LICENSE). Contributions are welcome — see [CONTRIBUTING.md](https://github.com/uptimely-ai/uptimely-core/blob/main/CONTRIBUTING.md).

## Feedback

We are happy to hear development ideas, bug reports and other form of feedback.

Find the contact details from [Uptimely website](https://uptimely.ai).
