# Development roadmap

Long term plans.


## Streaming

At the moment the framework is design for batch calculations.

We are planning to add streaming abstraction by data cache, watermarks and freshness.


## Support orchestrators

Currently the package supports only the built-in basic engine in a single process. It is sufficient only for examples.

Add support for common orchestrator patterns. Most likely requires Python decorator support for compiled functions and defining containers or vectorize environments (eg venv).


## Extend the MCP support

Add MCP support for each atomic analytical functions.
