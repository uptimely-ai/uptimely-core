# Modeling patterns

In industrial analytics pipelines, features must often be joined, aggregated, or reconciled across different datasets and dimensions.

Rather than inventing unique operation categories or ad-hoc join syntax for every variation, Uptimely Core maps these scenarios into a compact set of declarative concepts: **dimensions**, **entities**, **datasets**, and the five data-producing mapping kinds (`read`, `conform`, `expand`, `collapse`, `vectorize`).

This page outlines how common data integration and join patterns fit into the framework.

## Summary of join patterns

| Pattern | Scenario | Declarative mechanism | How it works |
| --- | --- | --- | --- |
| **Same-grain enrichment** | Combining features that share the same entity dimensions and row scope | Engine fragment merge | Automatic. Each returned fragment has the entity's dimension keys; the engine joins them incrementally. |
| **Lower-to-higher dimension (lookup)** | Enriching detailed observations with broader entity reference attributes | `expand` | The function receives the reference dataset, performs the broadcast or lookup, and returns the target dimension keys. |
| **Higher-to-lower dimension (summary)** | Summarizing granular observations into a coarser entity | `collapse` | The function groups the source data, calculates summaries, and returns the coarser target entity's keys. |
| **Row-scope reconciliation** | Aligning observations from another dataset within the same entity | `conform` | Adapts mismatched filters, time intervals, or grains to match the target dataset's row scope. |
| **Temporal & nearest-neighbor alignment** | Matching event timestamps or tolerance bands to telemetry | `expand`, `conform`, or `vectorize` | Uses native dataframe joins (such as Polars `join_asof()`) inside the function without needing a specialized operation kind. |
| **Unions & multi-source concatenation** | Loading multiple partitions, files, or tables into one dataset | `read` (source pushdown) | Handled at the data boundary via source SQL `UNION ALL` or `polars.concat()` within the read function. |

---

## 1. Same-grain enrichment

When features are calculated or retrieved at the exact same observation grain (for example, telemetry measurements and derived signals describing the same pump at the same timestamp), **no manual join is required**.

In Uptimely, all features belonging to an entity dataset share that entity's dimension keys. The engine accumulates features for each dataset incrementally:

1. Each data-producing mapping returns a dataframe containing the entity's dimension keys and its declared output columns.
2. The engine automatically merges each fragment into the dataset's accumulated working dataframe on those dimension keys.

No extra join mapping is needed between fragments of the same dataset. Different
datasets remain separate even if their entity and grain match: use an explicit
`conform` mapping to transfer features into the target row scope.

Returned keys must be unique. The engine full-joins non-vectorize fragments, so
unmatched observations may have null feature values. Vectorize results must
preserve the current dataset's exact observation keys.

---

## 2. Dimensional expansion (lookups)

A common industrial pattern is enriching high-frequency observations with low-frequency metadata. For example:
- Attaching rated pump flow or installation date (one row per pump) to minute-level telemetry (one row per pump and timestamp).
- Attaching plant environmental limits to line-level equipment sensors.

Use an **`expand`** mapping for this pattern:

```text
[Pump Reference Dataset]  (grain: pump)
          │
          │ expand
          ▼
[Pump Telemetry Dataset]  (grain: pump + timestamp)
```

In the specification, the mapping declares the function binding and target features:

```json
"mappings": {
    "expand_pump_reference": {
        "binding": {
            "function": "attach_pump_reference",
            "args": {
                "telemetry": "$datasets.@.dataframe",
                "reference": "$datasets.pump_reference.dataframe"
            }
        },
        "features": {
            "inputs": [
                "$features.bearing_temperature",
                "$features.reference_rated_flow",
                "$features.reference_installation_date"
            ],
            "outputs": ["$features.rated_flow", "$features.installation_date"]
        }
    }
}
```

Python authoring:

```python
from uptimely.analytics.python import bind, mapping, ref

expand_mapping = mapping.Expand(
    id="expand_pump_reference",
    inputs=[
        ref.feature("bearing_temperature"),
        ref.feature("reference_rated_flow"),
        ref.feature("reference_installation_date"),
    ],
    outputs=[ref.feature("rated_flow"), ref.feature("installation_date")],
    bind=bind.bind(
        attach_pump_reference,
        telemetry=ref.current_dataset().dataframe,
        reference=ref.dataset("pump_reference").dataframe,
    ),
)
```

These snippets assume the target dataset registers `rated_flow` and
`installation_date`, while the reference dataset registers
`reference_rated_flow` and `reference_installation_date`. Non-dimension features
need globally unique identifiers. Explicit inputs ensure that both reference
attributes and the target telemetry observations are available before the call;
passing a dataframe argument alone does not request all of its features.

The underlying Polars implementation:

```python
import polars as pl


def attach_pump_reference(telemetry: pl.LazyFrame, reference: pl.LazyFrame) -> pl.LazyFrame:
    """Broadcast pump attributes to telemetry rows using the shared pump dimension."""
    attributes = reference.select(
        "pump",
        pl.col("reference_rated_flow").alias("rated_flow"),
        pl.col("reference_installation_date").alias("installation_date"),
    )
    return telemetry.join(attributes, on="pump", how="left")
```

### Do you need to declare join keys?

**No.** In the specification, join keys are not declared on the mapping:

* The **target entity's dimensions** define the expected observation key contract.
* The function implementation receives the source dataset and current target dataset context.
* The function performs the join or broadcast internally and returns a dataframe matching the target entity's dimensions along with the declared output features.
* The engine merges the returned fragment directly into the target dataset.

The function still chooses its internal join keys explicitly (`pump` here).
Reference keys must be unique for this lookup to return unique target keys.
Dimension hierarchy metadata does not automatically select keys or join data.

---

## 3. Dimensional collapse (aggregations)

The inverse of expansion is analytical reduction: aggregating high-frequency observations to a coarser grain. For example:
- Calculating the maximum bearing temperature per pump over a 24-hour observation window.
- Summarizing machine operating hours per production line or plant.

Use a **`collapse`** mapping for this pattern:

```text
[Pump Telemetry Dataset]  (grain: pump + timestamp)
          │
          │ collapse
          ▼
[Pump Daily Summary]      (grain: pump)
```

In the specification:

```json
"mappings": {
    "bearing_temperature_by_pump": {
        "binding": {
            "function": "maximum",
            "args": {
                "dataset": "$datasets.pump_telemetry_dataset.dataframe",
                "column": "$features.bearing_temperature.id",
                "dimensions": ["$dimensions.pump.id"],
                "output": "$features.bearing_temperature_max.id"
            }
        },
        "features": {
            "inputs": ["$features.bearing_temperature"],
            "outputs": ["$features.bearing_temperature_max"]
        }
    }
}
```

Python authoring:

```python
from uptimely.analytics.python import bind, mapping, ref

collapse_mapping = mapping.Collapse(
    id="bearing_temperature_by_pump",
    inputs=[ref.feature("bearing_temperature")],
    outputs=[ref.feature("bearing_temperature_max")],
    bind=bind.bind(
        maximum,
        dataset=ref.dataset("pump_telemetry_dataset").dataframe,
        column=ref.feature("bearing_temperature").id,
        dimensions=[ref.dimension("pump").id],
        output=ref.feature("bearing_temperature_max").id,
    ),
)
```

The target dataset must register `bearing_temperature_max`. The source feature
`bearing_temperature` belongs to `pump_telemetry_dataset`; collapse inputs must
identify one source dataset, different from the target. The returned dataframe
includes `pump` even though dimension keys need not be repeated in `outputs`.
No separate `aggregate` function catalog or reducer bindings are required.

The function implementation groups by the target entity's dimensions and aggregates the metric:

```python
import polars as pl


def maximum(dataset: pl.LazyFrame, column: str, dimensions: list[str], output: str) -> pl.LazyFrame:
    """Group granular telemetry and compute aggregate maximum per entity dimension."""
    return dataset.group_by(dimensions).agg(pl.col(column).max().alias(output))
```

---

## 4. Row-scope reconciliation (conform)

Within the same entity, two datasets may share the same dimension keys but have different row scopes—such as different filtering rules, sampling intervals, or time coverage:

* A dataset containing continuous raw telemetry readings every second.
* A target dataset defined on clean, 5-minute resampled telemetry intervals.

Use a **`conform`** mapping to adapt observations from the existing dataset into the target dataset's required row scope before downstream calculations run:

```json
"mappings": {
    "conform_telemetry_5m": {
        "binding": {
            "function": "downsample_telemetry",
            "args": {
                "dataset": "$datasets.raw_telemetry.dataframe",
                "interval": "5m"
            }
        },
        "features": {
            "inputs": ["$features.pressure"],
            "outputs": ["$features.pressure_mean"]
        }
    }
}
```

Python authoring:

```python
from uptimely.analytics.python import bind, mapping, ref

conform_mapping = mapping.Conform(
    id="conform_telemetry_5m",
    inputs=[ref.feature("pressure")],
    outputs=[ref.feature("pressure_mean")],
    bind=bind.bind(
        downsample_telemetry,
        dataset=ref.dataset("raw_telemetry").dataframe,
        interval="5m",
    ),
)
```

The source dataset registers `pressure`, and the target registers
`pressure_mean`. Both datasets belong to the same entity, with observation keys
`pump` and `timestamp`; the function must return those columns along with
`pressure_mean`.

The underlying Polars implementation:

```python
import polars as pl


def downsample_telemetry(dataset: pl.LazyFrame, interval: str) -> pl.LazyFrame:
    """Resample high-frequency observations to regular time bins within the entity."""
    return (
        dataset.sort("timestamp")
        .group_by_dynamic("timestamp", every=interval, group_by="pump")
        .agg(pl.col("pressure").mean().alias("pressure_mean"))
    )
```

---

## 5. Temporal alignments and as-of joins

Industrial time-series data often requires matching measurements that do not share exact timestamps:
- Matching a discrete laboratory oil sample to the closest process telemetry reading.
- Looking up the active setpoint or recipe configuration valid at the time of each sensor reading.
- Correlating maintenance work orders with operational conditions immediately preceding the event.

Instead of introducing dedicated operation categories or specialized syntax for each temporal join variant, Uptimely handles these with native dataframe capabilities:

* **Between different datasets**: Use an **`expand`** mapping (if crossing dimension boundaries) or **`conform`** mapping (within the same entity).
* **Within the same dataset**: Use a **`vectorize`** mapping if both columns are already available in the accumulated dataset.

The function implementation uses Polars `join_asof()` (or database window queries) to execute the temporal match:

```python
import polars as pl


def align_closest_setpoint(
    telemetry: pl.LazyFrame,
    setpoints: pl.LazyFrame,
    output: str,
) -> pl.LazyFrame:
    """Perform an as-of join matching each reading to the latest prior setpoint."""
    return (
        telemetry.sort("timestamp")
        .join_asof(
            setpoints.sort("timestamp"),
            on="timestamp",
            by="pump",
            strategy="backward",
        )
        .select("pump", "timestamp", pl.col("target_value").alias(output))
    )
```

The function handles the alignment strategy (`backward`, `forward`, or `nearest`), tolerance windows, and column aliasing, and returns the target dimension keys plus the declared output feature.

This example assumes target dimensions `pump` and `timestamp`. Add every target
dimension if the entity has a larger key. Declare consumed telemetry and
setpoint features as mapping inputs; a dataframe argument alone does not
establish those feature dependencies. With `vectorize`, the result must retain
the current dataset's exact observation keys.

---

## 6. Unions and multi-source concatenation

Data often spans multiple physical tables, historical archives, or partitioned files:
- Combining live telemetry with long-term cold storage archives.
- Loading daily partitioned Parquet files (`telemetry_2026-10-*.parquet`).
- Ingesting identical sensor streams from multiple regional databases.

Concatenating rows (a union or append operation) is an **ingestion pattern**, not an analytical transformation. It should be handled at the system boundary inside the **`read`** function:

1. **Database pushdown**: In SQL sources, execute a `UNION ALL` directly in the source query so the database optimizes the retrieval.
2. **File and partition globbing**: In Python read functions, load multiple files and concatenate them with `polars.concat()` before returning the initial dataset fragment.

For example, a `read` mapping reading multi-partition parquet archives:

```python
import polars as pl


def read_archived_telemetry(archive_pattern: str) -> pl.LazyFrame:
    """Concatenate partitioned historical files at ingestion."""
    return pl.scan_parquet(archive_pattern)
```

This keeps analytical calculations focused purely on feature derivation, while data access functions absorb ingestion-level concerns.
