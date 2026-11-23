# Uptimely Core

Uptimely Core is an open source framework for managing interdependent data science calculations.

The goal is to free data science teams to focus on advanced analytics, mathematics, and modeling. Teams define their analytics in pure Python, while Uptimely Core minimizes the effort required for project setup, dependency modeling, debugging, testing, and validation.

Uptimely Core helps teams manage complex networks of analytical calculations, features, and dimensional hierarchies. Just as importantly, it makes dependencies on people, processes, and decisions easier to understand and manage.

The framework has focus on making calculations understandable at logical level. Other tools take responsibility of orchestration and execution.

Uptimely applies data-modeling best practices to organize data science into profiles. Each profile defines its dimensional grain, row scope, and set of features. Computational operators use profile metadata to define feature dependencies and bind functions, which are then used to materialize the resulting dataset.

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
* [Python API reference](https://uptimely-ai.github.io/uptimely-core/python/)
* [CLI API reference](https://uptimely-ai.github.io/uptimely-core/cli/)
* [MCP API and AI chat setup](https://uptimely-ai.github.io/uptimely-core/guides/ai-setup/)

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

**Go to your project root**.

Following commands assume `uv` Python environment. With Poetry use `poetry run uptimely <command>`. For other activated environment, just `uptimely <command>`.

Download the example project's code into the current directory without setup files.
The download does not overwrite existing files.

```sh
uv run uptimely example --no-setup --dir .
```

Create a build from the specification.

```sh
uv run uptimely build
```

Run the data science pipeline using the build.

```sh
uv run uptimely run
```

## Explore the project

Explore resources and results in the local web app:

```sh
uv run uptimely explore
```

Read more about [example project](https://uptimely-ai.github.io/uptimely-core/intro/example-project/) from the docs.

Open the project in a code editor, modify the code, build and run it again and explore the new results.

## Python API

The previous example was built by the [Python-authored example specification](https://github.com/uptimely-ai/uptimely-core/tree/main/example). The specification describes profiles, grains, features and operators. Functions remain pure Python.

Here is even more simplified example.

Put this to `src/functions.py`:

```python
import polars as pl


def read_values(dims: list[str], features: list[str]) -> pl.DataFrame:
    dataset = pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )
    return dataset.select(*dims, *features)


def double(dataset: pl.LazyFrame, value: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(value) * 2).alias(output))


def print_results(dataset: pl.DataFrame, dims: list[str], features: list[str]) -> None:
    print(dataset.select(*dims, *features))
```

Store this code to `spec/spec.py`:

```python
from src import functions
from uptimely import (
    Bind,
    Dimension,
    Operator,
    Profile,
    Resolution,
    Spec,
    ref,
)

measurement_id = Dimension(
    id="measurement_id",
    resolutions=[Resolution(id="measurement_id", key="id", type="integer")],
)


class MyAnalyticalProfile(Profile):
    grain = [measurement_id.resolution("measurement_id")]
    seed = "read_values"

    assembly = [
        Operator(
            id="read_values",
            compute=Bind(
                functions.read_values,
                dims=[ref.key("id")],
                features=[ref.output("value")],
            ),
        ),
        Operator(
            compute=Bind(
                functions.double,
                dataset=ref.dataset(),
                value=ref.input("value"),
                output=ref.output("doubled"),
            ),
        ),
        Operator(
            compute=Bind(
                functions.print_results,
                dataset=ref.dataset(),
                dims=[ref.key("id")],
                features=[ref.input("doubled")],
            ),
        ),
    ]


python_spec = Spec(
    profiles=[MyAnalyticalProfile],
    name="Analytics Specification",
)
```

Put this code in `run.py`.

```python
from uptimely import Uptimely

app = Uptimely()
app.build()
result = app.run()
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
