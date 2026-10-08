---
group: development
parent: Development
layout: default
title: Analytical functions
nav_order: 3
---

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

## Read from production

Fixing and degugging existing analytical solutions is often easiest by having 1:1 view for production data also during develpoment. This makes debugging much easier and prevents maintaining data in multiple environments manually.

Using non-production source makes sense when database structure requires changes, new algorithm is being developed or certain values are not yet in production.
