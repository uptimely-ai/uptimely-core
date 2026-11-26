# Uptimely best practices

## Profiles

Many data science teams stumble to the trap of standardization: Solutions are designed based on assumptions of clean data and world being static and standard.

But real life is full of exceptions, wanted or not.

For cooling pumps in a data center, exceptions could be:

- Maintenance period was not recorded
- A server-room sensor sends corrupted values within the normal operating range
- A cooling-pump drive was silently changed to twice the rated power without changes in the telemetry schema

Uptimely's hierarchical profiles bridges scalability with exceptional scenarios. You can create global default while overriding the result all the way to the most detailed resolution.

## Operators

When many features use the same calculation, create one operator per feature.
Each operator then records its own input and output dependency. Calculation
functions remain Python:

```python
import polars as pl


def double_single(dataset: pl.LazyFrame, feature: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(feature) * 2).alias(f"{feature}_doubled"))
```

Declare one operator for each source feature in YAML:

```yaml
assembly:
  double_signal_0:
    function: analytics:double_single
    inputs: [signal_0]
    outputs: [signal_0_doubled]
    args:
      feature: "$input.signal_0"
  double_signal_1:
    function: analytics:double_single
    inputs: [signal_1]
    outputs: [signal_1_doubled]
    args:
      feature: "$input.signal_1"
```

An alternative is one operator whose function accepts all the features:

```python
import polars as pl


def double_many(dataset: pl.LazyFrame, features: list[str], outputs: list[str]) -> pl.LazyFrame:
    return dataset.with_columns(
        [
            (pl.col(feature) * 2).alias(output)
            for feature, output in zip(features, outputs, strict=True)
        ]
    )
```

```yaml
assembly:
  double_all_signals:
    function: analytics:double_many
    args:
      features: ["$input.signal_0", "$input.signal_1"]
      outputs: ["$output.signal_0_doubled", "$output.signal_1_doubled"]
```

Both approaches materialize the same values. Separate operators give each
source feature its own input-output relationship. With one operator, lineage
associates its outputs with the full set of inputs, so downstream features can
appear dependent on all 100 signals.
