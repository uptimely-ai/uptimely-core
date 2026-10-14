# Examples

The examples demonstrate how Uptimely Core describes industrial analytics as a declarative specification, resolves feature dependencies, and produces executable plans and documentation.

## View the example documentation

From a repository checkout, build and serve the generated documentation website from example 1 with:

```sh
./scripts/serve-example-docs.sh
```

Open <http://localhost:8001/> to view it. Stop the server with **Ctrl+C**.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project defined by a JSON specification. |
| [`simple_analytics/`](simple_analytics/) | A small specification assembled in Python, converted through the canonical model, and exported to JSON. |

## Folder structure

```text
examples/
├── README.md
├── pump_analytics/
│   ├── data/                 Input and calculated example datasets
│   ├── functions/            Read, vectorize, and write function implementations
│   ├── _generated/           Plans, graphs, documentation, and engine output
│   ├── spec/                 Python specification declarations
│   ├── _generated/spec/     Exported declarative analytics specification
│   └── run_*.py              Example workflow entry points
└── simple_analytics/
	├── data/                 Data used by the Python example
	├── functions/            Example function implementations
	├── _generated/spec/      Exported specification output
	├── spec/                 Python specification declarations
	└── run_export_spec.py    Specification export entry point
```

## Quick start

With Python 3.13 or newer, install the package and download the examples:

```sh
pip install uptimely-core
uptimely examples download
python examples/check_setup.py
python examples/run_all.py
```

Run these commands from the parent of the downloaded `examples/` directory.
By default, the download uses the release tag matching the installed package
version (`v<version>`) and fails if that tag is unavailable. Use `--ref` to
select another branch, tag, or commit (`HEAD` selects the repository's default
branch), or `--output` to change the destination. The destination must not
already exist.

Generated artifacts are written beneath each example's `_generated/` directory.

See each example's README for details.
