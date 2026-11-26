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

**Recommended: install the CLI**

On Linux, macOS, and WSL, install the published Uptimely CLI for the current user:

```sh
curl -LsSf https://uptimely.ai/core/install.sh | sh
```

Restart your terminal, then confirm with `uptimely --help`. See the
[CLI setup guide](https://uptimely-ai.github.io/uptimely-core/guides/cli-setup/)
for installation locations, updates, and removal.

**Alternative: install in an existing Python environment**

Python 3.13 or newer is required. Install Uptimely Core with the command that
matches your tooling:

```sh
pip install uptimely-core
```

```sh
poetry add uptimely-core
```

```sh
uv add uptimely-core
```

To create a new environment with uv, see the
[Python environment setup guide](https://uptimely-ai.github.io/uptimely-core/guides/python-setup/).

## Build and run

**Go to your project root**.

Following commands assume CLI installation. With Python installation you might need to use eg `uv run uptimely <command>`.

Download the full example project into the current project directory. Existing
files are preserved, and the command stops if an example file would overwrite
one:

```sh
uptimely example
```

Create a build from the specification:

```sh
uptimely build
```

Run automated unit tests:

```sh
uptimely test
```

Materialize the calculation flow:

```sh
uptimely run
```

## Explore the project

Explore resources and results in the local web app:

```sh
uptimely explore
```

Read more about [example project](https://uptimely-ai.github.io/uptimely-core/intro/example-project/) from the docs.

Open the project in a code editor, modify the code, build and run it again and explore the new results.

## YAML specification

This minimal example uses Python functions and a YAML specification. Create a
new project folder, install Uptimely Core as described above, and add the
following files.

Set the source directory in `uptimely.toml`:

```toml
[code]
src = "code/src"
```

Put this in `code/src/functions.py`:

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

Store this as `spec/index.yaml`:

```yaml
name: Cooling Pump Specification
dimensions:
  measurement_id:
    resolutions:
      id:
        key: id
        type: integer
profiles:
  cooling_pump:
    grain: [measurement_id.id]
    seed: read_values
    assembly:
      read_values:
        function: functions:read_values
        outputs: [value]
        args:
          dims: [id]
          features: ["$output.value"]
      double:
        function: functions:double
        args:
          value: "$input.value"
          output: "$output.doubled"
      print_results:
        function: functions:print_results
        args:
          dims: [id]
          features: ["$input.doubled"]
```

From the project root, build and run the project:

```sh
uv run uptimely build
uv run uptimely run
```

The output shows `doubled` values of 20 and 40.

## Python API

It is possible to work with Uptomely objects through Python API. For example, load the built spec and list a profile's operators:

```python
# example
from uptimely import spec

document = spec.load_spec("artifacts/build/spec.json")
profile = document.profiles["cooling_pump"]
operators = list(profile.assembly)
print(f"cooling_pump has {len(operators)} operators: {', '.join(operators)}")
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
