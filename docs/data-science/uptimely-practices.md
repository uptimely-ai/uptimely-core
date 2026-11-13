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

When many features use the same calculation, create one operator per feature in
a loop. Each operator then records its own input and output dependency.

Create one operator per feature:

```python
import polars as pl
import uptimely as up


@up.function(returns="dataframe")
def double_single(dataset: pl.LazyFrame, feature: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(feature) * 2).alias(f"{feature}_doubled"))


def double_operator(index: int, source_feature: str) -> up.Operator:
    return up.Operator(
        id=f"double_signal_{index}",
        interface=up.Interface(outputs=[up.Feature(id=f"{source_feature}_doubled")]),
        compute=up.Binding(
            function=double_single,
            arguments={
                "dataset": up.ref.dataset(),
                "feature": up.ref.feature(source_feature),
            },
        ),
    )


source_features = [f"signal_{index}" for index in range(100)]
operators = [double_operator(index, feature) for index, feature in enumerate(source_features)]
```

Avoid one operator whose function accepts all 100 features:

```python
import polars as pl
import uptimely as up


@up.function(returns="dataframe")
def double_many(dataset: pl.LazyFrame, features: list[str], outputs: list[str]) -> pl.LazyFrame:
    return dataset.with_columns(
        [
            (pl.col(feature) * 2).alias(output)
            for feature, output in zip(features, outputs, strict=True)
        ]
    )


source_features = [f"signal_{index}" for index in range(100)]
output_features = [f"{feature}_doubled" for feature in source_features]

operator = up.Operator(
    id="double_all_signals",
    interface=up.Interface(
        outputs=[up.Feature(id=output) for output in output_features],
    ),
    compute=up.Binding(
        function=double_many,
        arguments={
            "dataset": up.ref.dataset(),
            "features": [up.ref.feature(feature) for feature in source_features],
            "outputs": output_features,
        },
    ),
)
```

Both approaches calculate the same values. The loop gives each operator a
separate input-output relationship. With one operator, lineage associates its
outputs with the full set of inputs, so downstream features can appear
dependent on all 100 signals.
