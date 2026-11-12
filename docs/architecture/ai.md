# AI agents and MCP

The MCP server lets an AI assistant work with an Uptimely analytics project.
An assistant can explain calculations, run a selected calculation with the
work it depends on, and inspect the latest execution's warnings and failures.

[MCP](https://modelcontextprotocol.io) is a standard way for an AI application
to call tools. The application supplies the chat interface and language model.
Uptimely supplies the project tools. The server does not require its own model
or model API key.

## Project access

One server process works with one analytics project. It reads the project's
saved build, containing the Spec and the plan prepared by the
[Compiler](compiler.md). Changes to source declarations become available after
a successful rebuild and a server reload.

The server does not build the project automatically. Missing or invalid builds
produce an error with a recovery command. Latest-run tools can read existing
run records without loading a build.

## Analytical execution

A function describes reusable Python code. An operator describes where that
function is used, which arguments it receives, and which features it needs.
Running through the operator allows the [Engine](engine.md) to prepare the
required data and run earlier calculations first.

An assistant can select a function when it has one matching use in the Spec.
When the same function is used in several places, the assistant must select
the intended profile and operator. This avoids guessing which calculation
the user meant.

Selected runs exclude later work, including configured output writers.
Explicitly selecting a writer still runs it. Full-build execution runs all
work in the saved plan. Read functions and custom calculations can also write
files or contact external services, so execution is not a read-only operation.

## Questions and results

The tools support three main kinds of question:

- **Explore the model:** "How many features does my spec have?" or
  "What does the pump health score depend on?"
- **Run analytics:** "Give me the pump optimization result" or
  "Run the pressure-flow ratio and show five rows."
- **Review execution:** "Which warnings were logged in the last engine run?"
  or "Which calculation failed?"

Results include a limited sample of rows with identifiers such as pump ID and
timestamp. Sampling limits response size, not the amount of data used by the
calculation. Functions must return data through their operator to expose
analytical rows. Results written only inside a function are not automatically
read back.

Every execution replaces the latest-run records, including logs and previews.
They describe the most recent run, including runs started through Python or
the command line, not a history of previous runs.

## Connection and boundaries

The client starts the server and communicates through its standard input and
output. No web port or separately managed background service is needed.
The server must run in a Python environment with access to the project,
its function packages, and its data.

Data freshness and date filtering are controlled by project sources. The
server does not interpret "today" as a filter. Only connect trusted projects
and review tool permissions in the client. Logs, previews, and chat answers
may contain project data.

## Learn more

See [MCP API](../mcp/index.md) for installation, VS Code and other client
configuration, working-directory requirements, connection checks, example
questions, and troubleshooting. Install the latest published MCP extra or use
the repository setup for unreleased tools. The
[Engine reference](engine.md) explains execution and saved run records.
