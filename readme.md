# Uptimely Core

Uptimely Core is an open source Python package for declarative numerical analytics with complex dependencies at scale.

It describes analytics workflows in a specification similar to OpenAPI, uses a declarative model inspired by Kubernetes. The framework generates plans, graphs, and documentation from that specification.

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

Install the package, download examples and run.

```sh
pip install uptimely-core
uptimely examples download
python examples/run_all.py
```

Explore the examples files, generated resources and modify for the needs of your own project.

## Documentation

Explore the [documentation site](https://uptimely-ai.github.io/uptimely-core/).

## Repository guide

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/index.md) | Architecture, specification, and development documentation. |
| [`examples/`](examples/README.md) | Runnable examples and generated artifacts. |
| [`scripts/`](scripts) | Code snippets for repository management |
| [`src/uptimely/`](src/uptimely/) | Package implementation for specifications, compilation, dependencies, documentation, and engine. |
| [`tests/`](tests/) | Automated tests for the package and examples. |

## Development

See
[CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

Released under the [MIT license](LICENSE). Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Feedback

We are happy to hear development ideas, bug reports and other form of feedback.

Find the contact details from [Uptimely website](https://uptimely.ai).
