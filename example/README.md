# Pump analytics example

This example shows how to use Uptimely Core to read pump data, calculate
operational measures, and view the results. It includes information about six
pumps, five model groups, three categories, sensor readings, and a small set
of external measurements.

## What the example does

- Combines pump details with sensor readings and configured values.
- Chooses a pump's capacity from its own value, its model group, or its
  category, in that order. It uses the first available value, not the largest.
  Capacities are measured in cubic metres per hour (m3/h).
- Shows the highest bearing temperature for each model group, category, minute,
  hour, and day.
- Runs a separate calculation using external measurements and saves its results
  to `_generated/pump_external_workflow_results.csv`.

The sample data has ten sensor readings across the six pumps. External
measurements are included for PUMP-101 and PUMP-201.
For example, PUMP-101 uses its own capacity of 125 m3/h even though its model
group has a value of 130 m3/h. PUMP-201 has no individual or model-group value,
so it uses its category's value of 100 m3/h. A capacity of zero is a valid
value, and a pump with no value at any level remains blank.

The example's importable Python modules are in `src/`: `analytics.py` contains
calculations, `io.py` handles file input and output, and `merge.py` defines
custom merge behavior.

## Quick start

Python 3.13 or newer is required.

Install Uptimely Core with pip:

```sh
pip install uptimely-core
```

Or add it to a Poetry project:

```sh
poetry add uptimely-core
```

When using Poetry, prefix the commands below with `poetry run`.

If you installed Uptimely Core outside this repository, download the example
files into a new `example` directory:

```sh
uptimely examples
```

Prepare the example for running:

```sh
uptimely build example
```

Repeat the build after changing the example files.

Run the calculations:

```sh
uptimely run example
```

## View the results

Start a local browser view of the example:

```sh
uptimely explore example
```

Open <http://127.0.0.1:8001/> in your browser.

To save a copy of the browser view and its data, export it to a folder or ZIP
file:

```sh
uptimely explorer export example --output pump-analytics-explorer
uptimely explorer export example --output pump-analytics-explorer.zip
```

For an explanation of the folders in an Uptimely project, see the
[project structure guide](https://uptimely-ai.github.io/uptimely-core/development/project-structure/).
