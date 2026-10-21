# Escape operation example

This small project demonstrates an explicitly uncontrolled operation. Its
function has no Python arguments, reads a local CSV again, calculates a ratio,
and writes a CSV internally. A preceding `read` mapping declares and loads the
input features; the escape binding does not receive that dataframe. Its mapping
still declares feature inputs and outputs so the spec and execution plan can
express dependencies; the written result is not materialized as a dataframe
column.

From the repository root, build and run the project:

```sh
poetry run uptimely project build --project-root examples/escape_operation --verbose
poetry run uptimely engine run --project-root examples/escape_operation
```

The output is written to
`examples/escape_operation/_generated/workflow_results.csv`. A successful
escape status reports only that the function returned without raising; it does
not verify the output file's contents. Downstream analytics that need this data
must use a separate `read` mapping with its own declared outputs. File or
database side effects do not implicitly order a read after an escape.
