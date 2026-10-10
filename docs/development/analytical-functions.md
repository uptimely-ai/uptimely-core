# Analytical functions

The framework creates many safeguards what can go into the analytical functions, and what comes out. For example dataset, feature and dimension data types, structural validation, operation types etc.

However, what happens inside the analytical functions written by user is developer's responsibility. It is possible to even produce structurally correct results with methods that are against the specification.

Here are the best practices for writing the analytical function.

## Avoid loops

There should be very little reasons to loop data within analytical functions.

Something like this should be a wakeup call:

```py
for truck in trucks:
    x = process_single_truck()
    ...
```

Most common reason for looping might be a "simulation" where each time step is dependent of the previous non-trivial calculation.

```py
for t in timesteps:
    results = complex_simulation_step(t, results)
    ...
```

For tabular data, prefer vectorized functions and SQL window capabilities where they fit the problem. In the specification, this feature category is named `vectorize`; each vectorize function should transform its declared feature inputs into one output feature without performing I/O.

## i/o only in read and write functions

For analytical functions, data should be passed only as input argument and the processed data should come through Python return. This gurantees function purity, takes benefit of automatic validation and makes code structure understandable for others.

Make clear separation between functions that perform analytics and those that communicate with data sources.

## Do the heavy lifting in the source

Data platforms such as Snowflake, Databricks, BigQuery, Spark, and relational databases are built for large-scale filtering, joining, deduplication, and aggregation. Let them do that work, and let read functions return only the slice that the analytical graph needs.

Push these operations into the source query of a read function:

* **Filtering** by asset, time range, and other row criteria
* **Column selection**, so only the required features are transferred
* **Joins** between large tables
* **Deduplication** and cleansing of raw data
* **Pre-aggregation** when the analytics only needs coarser data, such as hourly instead of per-second values

Loading a full table and filtering it afterwards in Python wastes network bandwidth, memory, and time. It also prevents the source from using its own optimizations.

Design source tables so that the common queries are efficient:

* Use **partitions** for the time dimension, so queries read only the requested periods
* Use **clustering** or **sort keys** for asset dimensions, so queries for one asset or asset group skip unrelated data
* Use **indexes** in relational databases for the columns used in filters and joins

Filter on the partitioned and clustered columns directly. Wrapping them in functions or casts may prevent the source from skipping data.

Expose the scope, such as identifiers and the time range, as read function arguments instead of hard-coding it in the query. Pass the values as bind parameters rather than formatting them into the SQL string, which prevents SQL injection. For example, a read function could send this query to the source:

```sql
select t.plant, t.production_line, t.pump, t.timestamp,
       t.flow_rate, t.discharge_pressure, p.rated_flow
from telemetry t
join pump_reference p on p.pump = t.pump
where t.pump = :pump               -- clustered column
  and t.timestamp >= :start        -- partitioned column
  and t.timestamp < :end
```

The source filters and joins the data, and only the requested rows and columns are returned. Bind parameter syntax depends on the database driver. Keep the read function free of analytical logic: it should define which data is retrieved, while `vectorize` and `collapse` functions define what is calculated from it.

## Read from production

Fixing and degugging existing analytical solutions is often easiest by having 1:1 view for production data also during develpoment. This makes debugging much easier and prevents maintaining data in multiple environments manually.

Using non-production source makes sense when database structure requires changes, new algorithm is being developed or certain values are not yet in production.
