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

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

Browse the [example project explorer](https://uptimely-ai.github.io/uptimely-core/example/).

More business benefits at [uptimely.ai website](https://uptimely.ai).

## Documentation

* [The full documentation site](https://uptimely-ai.github.io/uptimely-core/)
* [Python API reference](https://uptimely-ai.github.io/uptimely-core/reference/python/)
* [CLI API reference](https://uptimely-ai.github.io/uptimely-core/reference/cli/)
* [MCP API and AI chat setup](https://uptimely-ai.github.io/uptimely-core/reference/mcp/)

## Install

Python 3.13 or newer is required.

**For existing Python project**

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

Download the example project's code, data, and config without setup files:

```sh
uptimely example --no-setup --dir pump-analytics
```

Build and run the example:

```sh
uptimely build pump-analytics
uptimely run pump-analytics --preview 10
```

With Poetry or uv, prefix each `uptimely` command with `poetry run` or `uv run`.
The download does not overwrite existing files.

**For new project**

Download a version-matched example project and set up its environment with uv:

```sh
uvx --from uptimely-core uptimely example --dir pump-analytics
cd pump-analytics
uv sync
uv run uptimely build
uv run uptimely run --preview 10
```

Alternatively, fetch the full project template from the latest stable release:

```sh
curl -fLO https://uptimely.ai/core/example.zip
unzip example.zip -d pump-analytics
cd pump-analytics
uv sync
uv run uptimely build
uv run uptimely run --preview 10
```


Both workflows create an execution bundle under `_generated/build/`, then run
the data pipeline and preview its materialized profile frames:

![Uptimely run preview](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-run-preview.png)

Each run replaces `_generated/run/`.

The [example README](https://github.com/uptimely-ai/uptimely-core/blob/main/example/README.md)
describes the sample workflow and its project files. Follow the
[getting-started tutorial](https://uptimely-ai.github.io/uptimely-core/getting-started/tutorial/)
for setup, execution, and Explorer export.

## Explore the resources

Use the project explorer to inspect a project visually in web browser:

```sh
uptimely explore pump-analytics
```

For the new project above, run `uv run uptimely explore` inside `pump-analytics`.

Open <http://127.0.0.1:8001/> to view the Explorer.


## Python API

The previous example was built by the [Python-authored example specification](https://github.com/uptimely-ai/uptimely-core/tree/main/example). The specification describes profiles, grains, features and operators. Functions remain pure Python.

Here is even more simplified example.

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

The specification can be exported to `json`, and it works as a standalone semantic layer for data science.
Additionally Uptimely Core provides tooling to build portable execution plan and built-in engine to run and validate the workflow.

Create `run.py` in the project root and run it with `python run.py`.
The engine takes the built bundle, which contains the plan and its runtime
context. This is alternative to the previous CLI example:

```python
from uptimely import Engine, Project

project = Project()
bundle = project.build()
result = Engine(bundle).run()
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
