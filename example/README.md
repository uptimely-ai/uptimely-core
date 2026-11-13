# Data-center cooling pump analytics example

This example uses Uptimely Core to analyze six cooling-system pumps across two
data centers and four server rooms. It combines pump telemetry, asset metadata,
category and series rollups, and external measurements.

The sample data is synthetic. Health scores and operating-point recommendations
are illustrative calculations, not validated operating limits or control advice.

## Setup and installation

If you do not already have the example project, [install Uptimely Core](https://github.com/uptimely-ai/uptimely-core#install)
and download the example matching your installed version:

```sh
uptimely example --dir pump-analytics
```

The downloaded `pump-analytics/` directory is the example project.

Requires Python 3.13 or newer. Uptimely Core 0.10 is not yet
published, so installation will fail until it is available.

The installed example exposes its source modules under the Python package name
`example`.

### Dev container

With Docker and the VS Code Dev Containers extension installed, open the example folder
in VS Code and select **Dev Containers: Reopen in Container**.
The container installs uv and uses it to set up the example. Use uv to manage
the environment inside the dev container.

### Local setup

From the example project directory, choose one of the following.

**pip**

Use a Python 3.13 environment prepared for installing packages:

```sh
python3.13 -m pip install -e .
```

**Poetry**

```sh
poetry install
```

**uv**

```sh
uv sync
```

## Run the example

For a local Poetry setup, prefix the commands below with `poetry run`. For a
local uv setup, prefix them with `uv run`. In the dev container, run them
directly.

### Build and run

From the example project directory, prepare the example for running:

```sh
uptimely build
```

Repeat the build after changing the example files.

Run the calculations:

```sh
uptimely run
```

### View the results

Start a local browser view of the example:

```sh
uptimely explore
```

Open <http://127.0.0.1:8001/> in your browser.

To save a copy of the browser view and its data, export it to a folder or ZIP
file:

```sh
uptimely explorer export . --output cooling-pump-analytics-explorer

uptimely explorer export . --output cooling-pump-analytics-explorer.zip
```

For an explanation of the folders in an Uptimely project, see the
[folder structure guide](https://uptimely-ai.github.io/uptimely-core/architecture/folder-structure/).
