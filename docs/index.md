# Uptimely Core

Uptimely Core helps data science teams build, validate and run analytical pipelines with complex
input/output dependencies.

Use it for machine telemetry, process analytics, failure prediction, and
factory optimization. Currently works on batch, streaming abstractions are on the roadmap.

Definitions can be authored in Python and exported to JSON, or supplied directly as JSON. The built-in execution backend uses Polars, and the engine supports configurable runtime adapters.

> [!WARNING]
> This project follows semantic versioning, but is still at `0.x`: minor
> releases may include breaking changes. See the [changelog](https://github.com/uptimely-ai/uptimely-core/blob/main/CHANGELOG.md)
> for details.

## Demo

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

Browset the [example project explorer](https://uptimely-ai.github.io/uptimely-core/examples/pump_analytics/).

More business stuff at [uptimely.ai website](https://uptimely.ai).

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
uptimely build examples/pump_analytics --log-level debug --preview 10
uptimely run examples/pump_analytics
```

The build creates files
under `examples/pump_analytics/_generated/build/`. Rebuild after changing the
project source.

## Python API

Author a spec in Python by describing its profiles, grains, and assembly. Save
this module as `spec/spec.py` in an Uptimely project:

```python
import polars as pl
import uptimely as up


@up.function(kind="read")
def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


@up.function(kind="vectorize")
def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


@up.function(kind="write")
def print_results(dataset: pl.DataFrame) -> None:
    print(dataset)


measurement_id = up.Dimension(
    id="measurement_id",
    resolutions=[up.Resolution(id="measurement_id", key="id", type="integer")],
)


class CalculatedData(up.Profile):
    id = "calculated_profile"
    grain = [up.Grain(measurement_id, "measurement_id")]

    assembly = [
        up.Operator(
            id="read",
            interface=up.Interface(
                outputs=[
                    up.Feature(
                        id="value",
                        description="Input measurement for the calculation.",
                    )
                ],
            ),
            compute=up.Binding(function=read_values),
        ),
        up.Operator(
            id="double",
            interface=up.Interface(
                outputs=[
                    up.Feature(
                        id="doubled",
                        description="The input measurement multiplied by two.",
                    )
                ],
            ),
            compute=up.Binding(
                function=double,
                arguments={
                    "dataset": up.ref.data(),
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
                arguments={"dataset": up.ref.data()},
            ),
        ),
    ]


python_spec = up.Spec(
    profiles=[CalculatedData],
    name="Analytics Specification",
)
```

Then create `run.py` in the project root and run it with `python run.py`.
The engine takes the built bundle, which contains the plan and its runtime
context:

```python
from uptimely import Engine, project
from uptimely.engine import EngineConfig

bundle = project.build_project(".")
result = Engine(bundle, EngineConfig()).run()
```

Profiles declare operators in one assembly, optionally using a mapping to group them
by purpose. Each operator has an explicit ID unique within its profile. Grouping
is organizational, not execution order; dependencies determine execution.
In JSON specs, profiles declare their keyed action definitions under `actions`.

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
