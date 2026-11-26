# Uptimely Core

Uptimely Core brings a `dbt`-like workflow to data science. Define interdependent scientific calculations in Python and work with DataFrames instead of SQL and relational databases.

Declare analytics in Python, then build, test, and run them from the command line. Explore the results in your browser.

## Key features

- **Organize analytics:** Use Uptimely profiles to create semantic views for data science.
- **Trace calculations:** Follow column-level lineage through DataFrame processing.
- **Catch errors early:** Check processing-function signatures and validate specifications against real data.
- **Test and inspect results:** Run automated tests and visualize DataFrame results.
- **Build reusable algorithms:** Break complex algorithms into smaller, reusable operators.
- **Run consistently:** Use the same calculations across cloud and edge environments.
- **Model data clearly:** Apply dimensional-modeling best practices to data science.
- **Find guidance easily:** Keep up-to-date documentation close at hand.

## Use cases

- **Develop advanced calculations:** Structure work such as anomaly detection, signal processing, or quantum computing.
- **Compose workflows:** Manage many dependent calculations in one workflow.
- **Share calculation logic:** Reuse self-contained Uptimely operators across projects.
- **Work across environments:** Keep calculations consistent between cloud and edge.

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

Download the full example project into a new directory:

```sh
uv run uptimely example --dir pump-analytics
cd pump-analytics
```

The Uptimely project root keeps `uptimely.toml`, `spec/`, `data/`, and operator
test cases in `tests/`. Its `code/` folder is a separate Python source and
development environment. The commands below use the root environment. To use
the code environment instead, run them with `uv run --project code uptimely <command>`.

Create a build from the specification:

```sh
uv run uptimely build
```

Run automated unit tests:

```sh
uv run uptimely test
```

Materialize the calculation flow:

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

The previous example uses a [YAML-authored specification](https://github.com/uptimely-ai/uptimely-core/tree/main/example). Specifications describe profiles, grains, features and operators. Functions remain pure Python.

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

measurement = Dimension(
    id="measurement_id",
    resolutions=[Resolution(id="id", type="integer")],
)


class CoolingPump(Profile):
    grain = [measurement.at("id")]
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


spec = Spec(
    profiles=[CoolingPump],
    name="Cooling Pump Specification",
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
