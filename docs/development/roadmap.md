---
group: development
parent: Development
layout: default
title: Roadmap
nav_order: 4
---

# Development roadmap

## Data validation

Run data schema validation between functions.

Requires compatibility for basic operations of various dataframe implementations eg through `Ibis`.

## Streaming

At the moment the framework is design for batch calculations.

We are planning to add streaming abstraction by data cache, watermarks and freshness.


## Support orchestrators

Currently the package supports only the built-in basic engine in a single process. It is sufficient only for examples.

Add support for common orchestrator patterns. Most likely requires Python decorator support for compiled functions and defining containers or vectorize environments (eg venv).

## Publish in PyPi

Make the package available in Python package index.

## Runtime configuration enhancements

Environment-specific runtime resource substitution is already implemented.
The engine resolves `?<namespace>.<object>.<attribute>` placeholders against
`runtime_resources`, allowing the same compiled plan to run in dev, test, and
prod without changing its bindings or recompiling.

The Python API accepts a mapping; application code can load that mapping from
JSON. The MCP CLI already accepts a JSON file through `--runtime-resources`.
See [runtime overrides](../components/engine/index.md#runtime-overrides) for usage.

Future work includes automatic environment selection, layered configuration
merging, and a mechanism for calculation constants. Runtime resource substitution
does not currently override arbitrary specification fields or literal arguments.

## Add constants to spec

Add section to spec to define something like this:

```json
{
    "constants": {
        "gravity_m2s": 9.81
    },
    "entities": {
        "my_entity": {
            "my_dataset": {
                "vectorize": {
                    "physics_feature": {
                        "function": "gravity_calc",
                        "args": {
                            "gravity": "$constants.gravity_m2s"
                        }
                    }
                }
            }
        }
    }
}
```

## Add 2D lineage

Add traditional 2-dimensional column level lineage for features.

## MCP support

Add MCP support for each atomic function.
