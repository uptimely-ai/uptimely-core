# Uptimely Core

Uptimely Core is a data science framework for organizing data science work into
meaningful structure. It lets teams to build their analytical functions with pure Python, while adding a layer to build, validate, and run analytical
pipelines whose calculations depend on one another.

Uptimely complements data modeling: data models organize business data, while
Uptimely makes calculation-facing profiles and their feature dependencies
explicit. See [Data Modeling and Uptimely](docs/data-science/data-modeling.md).

Use it for machine telemetry, process analytics, failure prediction, and
factory optimization. Currently works on batch, streaming abstractions are on the roadmap.

Definitions can be authored in Python and exported to JSON, or supplied directly as JSON. The built-in execution backend uses Polars, and the engine supports configurable runtime adapters.

> [!WARNING]
> This project follows semantic versioning, but is still at `0.x`: minor
> releases may include breaking changes. See the [changelog](CHANGELOG.md)
> for details.

## Demo

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

Browse the [example project explorer](https://uptimely-ai.github.io/uptimely-core/examples/pump_analytics/).

More business benefits at [uptimely.ai website](https://uptimely.ai).

## Documentation

* [The full documentation site](https://uptimely-ai.github.io/uptimely-core/)
* [Python API reference](https://uptimely-ai.github.io/uptimely-core/python/)
* [CLI API reference](https://uptimely-ai.github.io/uptimely-core/cli/)

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

Build the project:

```sh
uptimely build examples/pump_analytics --log-level debug
```

The build creates the execution bundle under
`examples/pump_analytics/_generated/build/` and the Explorer data snapshot at
`examples/pump_analytics/_generated/explorer.json`. Rebuild after changing the
project source.

Execute the data pipeline:

```sh
uptimely run examples/pump_analytics --log-level debug --preview 10
```

Output will show the materialized profile frames:

![Uptimely run preview](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-run-preview.png)

Each execution replaces `_generated/run/` with run metadata, JSONL logs, and
bounded profile previews. Five preview rows are saved by default, including
for lazy frames; `--preview 10` saves and displays up to ten rows per profile.
This is a latest-run diagnostic snapshot, not a durable output store.

## Explore the resources

Use the project explorer to inspect a project visually:

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.


## Python API

The previous example was built by the [Python-authored example specification](examples/pump_analytics/). The specification describes profiles, dimensions, grains, and actions. Functions remain pure Python; the decorator supplies metadata for structural validation.

Here even more simplified example.

```python
import polars as pl
import uptimely as up


@up.function
def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


@up.function
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


@up.function
def print_results(dataset: pl.DataFrame) -> None:
    print(dataset)


measurement_id = up.Dimension(
    id="measurement_id",
    resolutions=[up.Resolution(id="measurement_id", key="id", type="integer")],
)


class MyAnalyticalProfile(up.Profile):
    id = "calculated_profile"
    grain = [measurement_id.resolution("measurement_id")]

    assembly = [
        up.Operator(
            id="read",
            interface=up.Interface(outputs=[up.Feature(id="value")]),
            compute=up.Binding(function=read_values),
        ),
        up.Operator(
            id="double",
            interface=up.Interface(outputs=[up.Feature(id="doubled")]),
            compute=up.Binding(
                function=double,
                arguments={
                    "dataset": up.ref.dataset(),
                    "value": up.ref.feature("value"),
                    "output": up.ref.feature("doubled"),
                },
            ),
        ),
        up.Operator(
            id="print",
            interface=up.Interface(outputs=[]),
            compute=up.Binding(
                function=print_results,
                arguments={"dataset": up.ref.dataset()},
            ),
        ),
    ]


python_spec = up.Spec(
    profiles=[MyAnalyticalProfile],
    name="Analytics Specification",
)
```

Then create `run.py` in the project root and run it with `python run.py`.
The engine takes the built bundle, which contains the plan and its runtime
context. This is alternative to the previous CLI example:

```python
from uptimely import Engine, project
from uptimely.engine import EngineConfig

bundle = project.build_project(".")
result = Engine(bundle, EngineConfig()).run()
```


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
