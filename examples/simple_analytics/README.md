# Python analytics example

This example uses a tiny synthetic dataset with an ID and two numeric inputs
per row. It calculates the sum of the inputs and adds a boolean tag for each
ID.

From the repository root, build and run the example:

```sh
poetry run uptimely project build --project-root examples/simple_analytics --verbose
poetry run uptimely engine run --project-root examples/simple_analytics
```
