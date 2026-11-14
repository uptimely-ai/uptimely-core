# Uptimely Core

Uptimely Core is an open source framework for managing interdependent data science calculations.

The ambition is to free data science teams from building internal tools to define, debug, validate and deploy their work, so they can focus on advanced analytics, mathematics, and modeling.

The framework lets teams to build their analytics with pure Python functions. It is specialized to manage analytical pipelines whose calculations depend on one another either by calculated features or dimensional hierarchy.

Uptimely takes best practices from data modeling to organize data science into **profiles**: Analytical declarations on different grains. The profiles makes their meta data available to computational **operators** declaring feature dependencies and function bindings.

Author the data science workflow in Python. Build and run from command line. Explore from web browser.

> [!WARNING]
> This project is still at version `0.x`: minor
> releases may include breaking changes. See the [changelog](https://github.com/uptimely-ai/uptimely-core/blob/main/CHANGELOG.md)
> for details.

## Demo

Browse the [example project explorer](https://uptimely-ai.github.io/uptimely-core/example/).

Screenshot from the web explorer:

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

Materialized results from Uptimely engine run:

![Uptimely run preview](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-run-preview.png)

More business benefits at [uptimely.ai/core/](https://uptimely.ai/core/).

## Documentation

* [The full documentation site](https://uptimely-ai.github.io/uptimely-core/)
* [Python API reference](https://uptimely-ai.github.io/uptimely-core/reference/python/)
* [CLI API reference](https://uptimely-ai.github.io/uptimely-core/reference/cli/)
* [MCP API and AI chat setup](https://uptimely-ai.github.io/uptimely-core/reference/mcp/)

## Install

Python 3.13 or newer is required.

**Install in existing Python environment**

Install Uptimely Core with the command that matches your tooling:

```sh
pip install uptimely-core
```

```sh
poetry add uptimely-core
```

```sh
uv add uptimely-core
```

**Create a new Python environment**

Go to your project directory.

If uv is not installed, [install it](https://docs.astral.sh/uv/getting-started/installation/) on macOS or Linux:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your shell if `uv` is not found.

```sh
uv init --bare --python 3.13
uv add uptimely-core
```

## Build and run

Go to your project root. The following commands assume an active Python environment.

For Poetry use `poetry run uptimely <command>`.

For uv use `uv run uptimely <command>`.

Download the example project's code into the current directory without setup files.
The download does not overwrite existing files.

```sh
uptimely example --no-setup --dir .
```

Create a build from the specification.

```sh
uptimely build
```

Run the data science pipeline using the build.

```sh
uptimely run
```

Explore resources and results in the local web app:

```sh
uptimely explore
```

## Next steps

The [getting started tutorial](https://uptimely-ai.github.io/uptimely-core/getting-started/tutorial/) provides more information about launching an Uptimely project.

Open the project in a code editor, modify the code, run it again and explore the new results.

## Python API

The previous example was built by the [Python-authored example specification](https://github.com/uptimely-ai/uptimely-core/tree/main/example). The specification describes profiles, grains, features and operators. Functions remain pure Python.

Here is even more simplified example.

Store this code to `spec/spec.py`

```python
import polars as pl
import uptimely as up


def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


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

Put this code in `run.py`.

```python
from uptimely import Engine, Project

project = Project()
bundle = project.build()
result = Engine(bundle).run()
```

Run in Python:

```sh
python run.py
```

## Repository guide

| Path | Purpose |
| --- | --- |
| [`docs/`](https://github.com/uptimely-ai/uptimely-core/tree/main/docs) | Architecture, specification, and development documentation. |
| [`example/`](https://github.com/uptimely-ai/uptimely-core/tree/main/example) | Runnable examples and generated artifacts. |
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
