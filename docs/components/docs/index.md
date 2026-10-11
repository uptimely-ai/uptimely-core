# Analytics documentation

Uptimely generates documentation from an
[Open Analytics Specification](../../specification/index.md). Feature definitions,
function bindings, and declared dependencies become a static website with three
connected views:

| Page | Purpose |
| --- | --- |
| Specification | Separate Overview, Features, Dimensions, and Functions pages, linked beneath Specification in the sidebar. |
| Feature lineage | Explore logical dependencies in interactive 2D and 3D views. |
| Execution plan | Overview summary, 2D and 3D callable graphs, and detailed parallel execution stages. |

The documentation is about
analytics project, not the Uptimely package itself.

![Specification reference overview](../../assets/img/open-analytics-specification-overview.png)

## Generate the website

### Command line

```sh
uptimely docs generate --spec _generated/spec/spec.json
```

The command exports this directory:

```text
_generated/docs/
├── index.html
├── spec.html
├── spec_features.html
├── spec_dimensions.html
├── spec_functions.html
├── feature_graph_2d.html
├── feature_graph_3d.html
├── execution_plan.html
├── execution_plan_graph_2d.html
├── execution_plan_graph_3d.html
└── execution_plan_stages.html
```

Start at `index.html`. `spec.html` contains the specification overview; the other
specification pages contain only their respective sections. The Specification
sidebar group provides subnavigation and highlights the current section.
Feature graph provides separate 2D and 3D lineage views in its sidebar
subnavigation.
Execution plan has Overview, 2D graph, 3D graph, and Stages subnavigation.
Overview contains summary counts; the graph pages show compiled callable
operations and their dependencies, rather than feature-lineage nodes.
Stages lists dependency-ordered operations with their arguments and return types.
Standalone execution-plan exports keep the summary, 3D callable graph, and
stages in one HTML document.
Each report is a complete HTML page, with relative links to
the other reports. The directory can be moved or hosted beneath a URL prefix
without rebuilding its page navigation.

The generation options are:

| Option | Behavior |
| --- | --- |
| `--spec` | Required path to a JSON specification. |
| `--output` | Website directory; defaults to `_generated/docs`. |
| `--project-root` | Directory added to Python's import path; defaults to the working directory. |
| `--include-generated-at` | Show a build timestamp on the specification page. |

For a project outside the working directory:

```sh
uptimely docs generate \
  --spec analytics/_generated/spec/spec.json \
  --project-root analytics \
  --output public/analytics
```

Specification and output paths are relative to the working directory, not to
`--project-root`. The import root lets Uptimely inspect the declared function
entrypoints when compiling the execution plan.

Generation imports function modules and inspects signatures, but does not invoke
analytical functions or run the engine. Use trusted specifications and
implementations, with their dependencies installed. Invalid specifications,
compilation failures, and export errors produce an error message and a nonzero
exit status.

### Python API

```python
from uptimely.docs.docs import Documentation
from uptimely.spec import Specification

specification = Specification.from_json("_generated/spec/spec.json")
documentation = Documentation(specification)
index_path = documentation.create_html()
```

The generator also accepts an in-memory `Specification`; no source JSON path is
required. Function entrypoints must still be importable.

Unlike the CLI's `--output` directory, the Python API's `output_path` is an
**index-file path**:

```python
index_path = documentation.create_html(
    output_path="public/analytics/index.html",
)
```

All reports and specification section pages are written beside the index. The
index filename cannot match any of the six report filenames shown above, because
those names are reserved for the reports.

Timestamps are disabled by default for reproducible exports. Pass
`include_generated_at=True` to display one on each specification section page.

## Preview and publish

```sh
uptimely docs serve
```

This serves an existing `_generated/docs/` website at
<http://127.0.0.1:8001/>. Port **8001** is separate from the project documentation's
MkDocs preview on port **8000**.

| Option | Behavior |
| --- | --- |
| `--directory` | Website directory; defaults to `_generated/docs`. Must contain `index.html`. |
| `--host` | Bind address; defaults to `127.0.0.1`, restricting access to the local machine. |
| `--port` | TCP port; defaults to `8001`. Use `0` to select an available port. |

The server prints its address at startup. Stop it with **Ctrl+C**. It serves
existing files; it does not generate, watch, or rebuild the website.

For the end-to-end example, run from the repository root:

```sh
poetry run uptimely docs generate \
  --spec examples/example_1/_generated/spec/spec.json \
  --output examples/example_1/_generated/docs
poetry run uptimely docs serve --directory examples/example_1/_generated/docs
```

Visit <http://localhost:8001/>.

The preview server has no authentication or TLS and is not intended for
production hosting. Binding to `0.0.0.0` exposes files on all IPv4 interfaces.
Serve only a directory intended for publication, without sensitive files or
symlinks to private content.

For deployment, publish the generated directory through a static web host. No
Python application server is needed. Use authenticated hosting for private
specifications. The pages currently load styling, fonts, icons, and graph
libraries from external services; full styling and visualization require network
access.

## Understand the feature graph

### Logical dependencies versus physical data flow

A warehouse schema, ETL diagram, or execution trace describes where data is
stored or processed. It does not necessarily explain what a feature means or
which other features it depends on.

For example, a table containing values for `A` and `B` does not reveal that a
calculation produces `B` from `A`, what their types are, or which downstream
features consume `B`. Reading `calculate_b(a)` in Python also leaves questions
about its inputs, outputs, and surrounding workflow.

The specification declares those relationships explicitly. Uptimely visualizes
them without trying to infer arbitrary Python behavior from source code. The
graph reflects the declared model, not dependencies or side effects that
functions leave undeclared.

### 3D lineage

The interactive 3D graph uses:

- **Blue spheres** for features, including source-provided and calculated features.
- **Octahedra colored by operation type** for functions.
- **Directed arrows** for dependency connections.

The legend identifies read, vectorize, collapse, conform, expand, and write
functions. Select a node to inspect its feature or function metadata.

### 2D lineage

Choose a 2D left-to-right lineage view when you want to follow upstream inputs
through calculations to downstream features. It uses layered node cards,
directional links, and a fit-to-view control. Both renderings include the same
node details and can be exported with `FeatureGraph.export_html`:

```python
graph.export_html("_generated/graph/feature_graph_2d.html", dimension="2d")
graph.export_html("_generated/graph/feature_graph_3d.html", dimension="3d")
```

The `dimension` argument defaults to `"3d"`, preserving the existing output.

The feature graph explains logical lineage; the
[execution plan](../compiler/index.md) separately shows callable dependencies and
execution stages.

### Focus on a feature

The Python graph API can export the upstream dependency subset needed for a
selected feature:

```python
from uptimely.analytics import FeatureGraph

graph = FeatureGraph(specification)
subset = graph.subset(["health_signal_normalized"])
subset.export_html("_generated/graph/health_signal.html")
```

This is useful for debugging, reviewing a calculation, or sharing a smaller
lineage view. Website generation exports full 2D and 3D feature graphs; subset reports
are created separately through the Python API.

## Standalone reports and reference data

The individual HTML exporters remain available without website navigation:

```python
from uptimely.analytics import FeatureGraph
from uptimely.compile import Compiler

specification.create_html()  # _generated/spec/spec.html
FeatureGraph(specification).export_html("_generated/graph/feature_graph.html")
Compiler(specification).compile().export_html()  # _generated/compile/execution_plan.html
```

Each exporter accepts an explicit output-file path.
`Specification.create_html` is the standalone specification reference exporter
previously provided by `Documentation.create_html`. The latter now exports the
complete website and returns its index path. The standalone specification export
remains a single HTML file containing all four sections and local anchor navigation.

Reference JSON is a separate export:

```python
data_path = documentation.create_json()  # _generated/docs/docs.json
```

It contains the specification configuration, summary counts, feature
dependencies, and optional generation timestamp. Neither `Documentation.create_html`
nor `uptimely docs generate` automatically writes this JSON. The example's
`run_docs.py` calls both exports.

![Specification feature reference](../../assets/img/open-analytics-specification-features.png)

See the [Python API reference](../../reference/api.md#analytics-documentation) for
the documentation interface and the
[feature graph API](../../reference/api.md#dependency-graphs) for graph operations.

## Template organization

All HTML reports use Jinja templates in `src/uptimely/templates/`. The root
`base.html.j2` provides the shared layout and optional website navigation.
The root `index.html.j2` renders the website landing page. Subdirectories group
the specification reference, individual page templates, and shared sections (`spec/`),
feature graph (`graph/`), and
execution plan (`plan/`).

Renderers stay in their component modules and share the package template loader
in `uptimely.render`. Template inheritance and includes use paths relative to the
central template directory, such as `spec/sections/entities.html.j2`. The
templates are included in the installed Python package, so both standalone
exports and website generation work outside a repository checkout.
