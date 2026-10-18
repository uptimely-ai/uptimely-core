# Development roadmap

## Data validation

Run data schema validation between functions.

Natural place in projet structure could be `/validations` folder.

## Streaming

At the moment the framework is design for batch calculations.

We are planning to add streaming abstraction by data cache, watermarks and freshness.


## Support orchestrators

Currently the package supports only the built-in basic engine in a single process. It is sufficient only for examples.

Add support for common orchestrator patterns. Most likely requires Python decorator support for compiled functions and defining containers or vectorize environments (eg venv).



## Runtime configuration enhancements

Environment-specific runtime configuration substitution is already implemented.
The engine resolves `?<namespace>.<object>.<attribute>` placeholders against
`bind`, allowing the same compiled plan to run in dev, test, and
prod without changing its bindings or recompiling.

The Python API accepts a mapping; application code can load that mapping from
JSON. The MCP CLI already accepts a JSON file through `--config`.
See [runtime overrides](../components/engine.md#runtime-overrides) for usage.

Future work includes automatic environment selection, layered configuration
merging, and a mechanism for calculation constants. Runtime configuration
substitution does not currently override arbitrary spec fields or
literal arguments.

## Extend the MCP support

Add MCP support for each atomic analytical functions.

## Add parameters to spec

Parameter would be another column type aside of dimensions and features.

It could be described as a control variable for spec: It is participating to calculation and enables configuration per dimension, but is not intended to be modified in the process.

A constant could be used as a parameter.

## Add constants to Spec

Add a section to Spec to define something like this:

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

Before implementation, evaluate if this is just a special case for parameters.

And whether constants and parameters should be stored among other data, not in the Spec document.
