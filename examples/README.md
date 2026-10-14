# Examples

The examples demonstrate how Uptimely Core describes industrial analytics as a declarative specification, resolves feature dependencies, and produces executable plans and documentation.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`example_1/`](example_1/) | An end-to-end pump analytics project defined by a JSON specification. |
| [`example_2/`](example_2/) | A small specification assembled in Python, converted through the canonical model, and exported to JSON. |

## Folder structure

```text
examples/
├── README.md
├── example_1/
│   ├── data/                 Input and calculated example datasets
│   ├── functions/            Read, vectorize, and write function implementations
│   ├── _generated/           Plans, graphs, documentation, and engine output
│   ├── spec/                 Python specification declarations
│   ├── _generated/spec/     Exported declarative analytics specification
│   └── run_*.py              Example workflow entry points
└── example_2/
	├── data/                 Data used by the Python example
	├── functions/            Example function implementations
	├── _generated/spec/      Exported specification output
	├── spec/                 Python specification declarations
	└── run_export_spec.py    Specification export entry point
```

## Quick start

### Download examples with the installed package

With Python 3.13 or newer, install the package and download matching release
examples without cloning the repository:

```sh
pip install uptimely-core==0.1.0
uptimely examples download --ref v0.1.0
python examples/check_setup.py
python examples/run_all.py
```

Run these commands from the parent of the downloaded `examples/` directory.
The download copies only the public GitHub repository's root-level `examples/` contents,
including data and specifications. It does not execute downloaded code.
Empty directories are not copied.

The source repository comes from the installed package's `Repository` metadata,
which is configured in [`pyproject.toml`](../pyproject.toml). By default the command
downloads the repository's current default branch. To select a release tag,
branch, or commit, or to use a different destination:

```sh
uptimely examples download --ref v0.1.0 --output ./demo/examples
cd demo
python examples/run_all.py
```

The commands above pair package version `0.1.0` with release tag `v0.1.0`.
If you install a different version, select its matching release tag with `--ref`.
Omitting `--ref` downloads the default branch, which may contain unreleased
changes incompatible with your installed package. The destination must not
already exist, even if it is empty. Download and extraction errors produce a
nonzero exit status without leaving a partially extracted destination.

### Run examples from a repository checkout

1. Clone the repository and change into its directory:

	```sh
	git clone https://github.com/uptimely-ai/uptimely-core.git
	cd uptimely-core
	```

2. Open the repository in its `.devcontainer/` with VS Code, or create a Python environment from [`pyproject.toml`](../pyproject.toml). With Poetry, install the project dependencies with:

	```sh
	poetry install
	```

3. Check the environment and run every workflow from the repository root:

```sh
poetry run python examples/check_setup.py
poetry run python examples/run_all.py
```

The individual workflows can also be run directly:

```sh
poetry run python -m examples.example_1.run_execution_plan
poetry run python -m examples.example_1.run_export_spec
poetry run python -m examples.example_1.run_docs
poetry run python -m examples.example_1.run_feature_graph
poetry run python -m examples.example_1.run_engine
poetry run python -m examples.example_2.run_export_spec
```

The execution plan, feature graph, and engine runners print a concise summary by default. Add `--verbose` to any of those commands when you need dependency graphs, execution stages, or dataset details.

Only `run_docs.py` generates HTML, always as the complete website. Specification
and execution-plan runners export JSON; the feature-graph runner inspects full
and subset graphs without exporting files.

Generated artifacts are written beneath each example's `_generated/` directory:

| Output | Command |
| --- | --- |
| [`example_1/_generated/compile/execution_plan.json`](example_1/_generated/compile/execution_plan.json) | `run_execution_plan.py` |
| [`example_1/_generated/spec/spec.json`](example_1/_generated/spec/spec.json) | `run_export_spec.py` |
| [`example_1/_generated/docs/docs.json`](example_1/_generated/docs/docs.json) | `run_docs.py` |
| [`example_1/_generated/docs/index.html`](example_1/_generated/docs/index.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/overview.html`](example_1/_generated/docs/spec/overview.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/features.html`](example_1/_generated/docs/spec/features.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/entities.html`](example_1/_generated/docs/spec/entities.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/datasets.html`](example_1/_generated/docs/spec/datasets.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/dimensions.html`](example_1/_generated/docs/spec/dimensions.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/functions.html`](example_1/_generated/docs/spec/functions.html) | `run_docs.py` |
| [`example_1/_generated/docs/spec/graph.html`](example_1/_generated/docs/spec/graph.html) | `run_docs.py` |
| [`example_1/_generated/docs/plan/overview.html`](example_1/_generated/docs/plan/overview.html) | `run_docs.py` |
| [`example_1/_generated/docs/plan/graph.html`](example_1/_generated/docs/plan/graph.html) | `run_docs.py` |
| [`example_1/_generated/docs/plan/stages.html`](example_1/_generated/docs/plan/stages.html) | `run_docs.py` |
| [`example_1/_generated/docs/execution/data_lineage.html`](example_1/_generated/docs/execution/data_lineage.html) | `run_docs.py` |
| [`example_2/_generated/spec/spec.json`](example_2/_generated/spec/spec.json) | `run_export_spec.py` |

The scripts are intended to run from the repository root. Python 3.13 or newer is required. See each example's README for its specification model and workflow details.

For website generation, customization, and preview instructions, see the
[analytics documentation](../docs/components/docs/index.md) and the
[Python API reference](../docs/reference/api.md#analytics-documentation).

From a repository checkout, build and serve the example website with:

```sh
./scripts/serve-example-docs.sh
```

Open <http://localhost:8001/> and stop the server with **Ctrl+C**. The script
uses Poetry and the example's exported specification, works from any working
directory, and rebuilds the full website before serving it. Server options can
be passed through, for example `./scripts/serve-example-docs.sh --port 8002`.
