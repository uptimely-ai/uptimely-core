# Example 2: Python Specification Export

`example_2` is a small, self-contained example of declaring a dataset in Python. It defines one `read` fragment with input features, two `vectorize` operations, one `write` operation, and an explicit row context.

## How the specification is read

The specification is declared in [`spec/spec.py`](spec/spec.py). It imports the example functions and dimensions, creates a `Dataset`, and registers those parts with `Specification.from_python(...)`. The runner [`run_export_spec.py`](run_export_spec.py) imports that specification setup and writes the resulting JSON to `_generated/spec/spec.json`.

## Exporting the specification

Run `poetry run python -m examples.example_2.run_export_spec` from the
repository root to export the canonical JSON specification to
`examples/example_2/_generated/spec/spec.json`. For environment setup and
running workflows, see the shared [examples guide](../README.md).
