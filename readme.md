# Uptimely Core

Uptimely Core helps industrial teams build and run batch analytics with complex
feature dependencies.

Use it for machine telemetry, process analytics, failure prediction, and
factory optimization. Streaming abstractions are on the roadmap.

Definitions can be authored in Python and exported to JSON, or supplied directly as JSON. The built-in execution backend uses Polars, and the engine supports configurable runtime adapters.

> [!WARNING]
> This project follows semantic versioning, but is still at `0.x`: minor
> releases may include breaking changes. See the [changelog](CHANGELOG.md)
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
uptimely build examples/pump_analytics --verbose --preview 10
uptimely run examples/pump_analytics
```

The build creates files
under `examples/pump_analytics/_generated/build/`. Rebuild after changing the
project source.

## Python API

Author a spec in Python by describing its entity, dataset, and actions.
This small example reads two rows and defines a derived feature:

```python
import polars as pl

from uptimely.spec.python import (
    Action,
    Dataset,
    Dimension,
    Entity,
    Feature,
    PythonSpec,
    function,
    ref,
)


@function(kind="read")
def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


@function(kind="vectorize")
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


class CalculatedData(Dataset):
    id = "calculated_dataset"
    entity = "measurements"

    producers = [
        Action(
            id="read",
            function=read_values,
            arguments={},
            outputs=[Feature(name="value")],
        ),
        Action(
            id="double",
            function=double,
            arguments={
                "dataset": ref.current_dataset().dataframe,
                "value": ref.feature("value"),
                "output": ref.feature("doubled").id,
            },
            outputs=[Feature(name="doubled")],
        ),
    ]


definition = PythonSpec(
    dimensions=[Dimension(id="id", type="integer")],
    entities=[
        Entity(
            id="measurements",
            name="Measurements",
            dimensions=["id"],
        )
    ],
    datasets=[CalculatedData],
    name="Analytics Specification",
)
specification = definition.to_model()
```

Datasets group actions into `producers` (feature-producing kinds), `publishers`
(`write`), and `pipelines` (`escape`, for opaque custom workflows). Each action
has an explicit ID unique within its dataset. These lists declare roles, not
execution order; dependencies determine execution.

## Further exploration

Use the project explorer to inspect a project visually:

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.

See the [documentation site](https://uptimely-ai.github.io/uptimely-core/) for
the full guides, and the [Python API reference](docs/python/index.md) for
public classes, functions, and signatures.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/index.md) | Architecture, specification, and development documentation. |
| [`examples/`](examples/README.md) | Runnable examples and generated artifacts. |
| [`scripts/`](scripts) | Code snippets for repository management |
| [`src/uptimely/`](src/uptimely/) | Package implementation for analytics, compilation, dependencies, documentation, and execution. |
| [`tests/`](tests/) | Automated tests for the package and examples. |

## Development

See
[CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

Released under the [MIT license](LICENSE). Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Feedback

We are happy to hear development ideas, bug reports and other form of feedback.

Find the contact details from [Uptimely website](https://uptimely.ai).
