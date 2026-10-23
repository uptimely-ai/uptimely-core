# Uptimely Core

Uptimely Core is an open source Python package for declarative numerical
analytics with complex dependencies at scale.

Analytics definitions describe workflows in JSON, using a declarative model
inspired by OpenAPI and Kubernetes. The compiler generates plans from the
analytics; the package can also render dependency graphs and documentation.

Ships with simple engine and plans to integrate to common execution backends.

The package has been developed especially for industrial organizations working with cases such as machine telemetry, process analytics, failure prediction and factory optimization.

Currently the examples are built around batch processing. Streaming abstractions are not available yet.

> [!WARNING]
> This project follows semantic versioning, but is still at `0.x`: minor
> releases may include breaking changes. See the [changelog](CHANGELOG.md)
> for details.

## Demo

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-demo.gif)

Read more at [uptimely.ai website](https://uptimely.ai).

## Quick start

Python 3.13 or newer is required.

### Install

With pip:

```sh
pip install uptimely-core
```

With poetry:

```sh
poetry add uptimely-core
```

With poetry, add `poetry run` before the following commands.

### Download examples

Download example files `examples` directory:

```sh
uptimely examples
```

### Build the spec

The build creates files under `examples/pump_analytics/_generated/build/`.
Rebuild after changing the example's source files.

```sh
uptimely build examples/pump_analytics --verbose
```

### Run the calculations

Engine reads the build and executes the calculation by the compiled plan.

```sh
uptimely run examples/pump_analytics
```

### Open the project explorer

Visually explore the project resources.

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.


## Documentation

Explore the [documentation site](https://uptimely-ai.github.io/uptimely-core/).

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
