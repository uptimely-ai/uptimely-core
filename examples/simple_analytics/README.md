# Python analytics example

This example uses a tiny synthetic dataset with an ID and two numeric inputs
per row. It calculates the sum of the inputs and adds a boolean tag for each
ID.

From the repository root, build and run the example:

```sh
poetry run uptimely build examples/simple_analytics --verbose
poetry run uptimely run examples/simple_analytics
```
