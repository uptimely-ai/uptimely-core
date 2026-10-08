# Example 2: Python Specification Export

`example_2` is a small, self-contained example of declaring a dataset in Python. It defines one `read` fragment with input features, two `vectorize` operations, one `write` operation, and an explicit row context.

## How the specification is read

The specification is declared in [`spec/spec.py`](spec/spec.py). It imports the example functions and dimensions, creates a `Dataset`, and registers those parts with `Specification.from_python(...)`. The runner [`run_export_spec.py`](run_export_spec.py) imports that specification setup and writes the resulting JSON to `generated/spec.json`.

## How to run

Run the export command from the project root:

```sh
poetry run python examples/check_setup.py
poetry run python -m examples.example_2.run_export_spec
```

The generated specification is written to `examples/example_2/generated/spec.json`.

## Folder structure

| Folder or file | Description |
| --- | --- |
| `spec/spec.py` | Python declarations for the dataset, inputs, calculations, and dimensions. |
| `functions/functions.py` | Function catalog used by the specification bindings. |
| `data/data.py` | In-memory example data. |
| `run_export_spec.py` | Builds and exports the specification. |
| `generated/` | Exported specification output. |
