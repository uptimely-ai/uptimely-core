---
group: components
layout: default
title: AI Agents
parent: Components
nav_order: 3
has_children: false
---

# Working with AI Agents

Uptimely Core is built from ground up to natively run and manage numerical calculations with AI agents.

AI assistants can explore an analytics project without custom integration code.

Specifications are declarative JSON, functions
are catalog entries with typed arguments, and plans are portable — the same
artifacts an agent can read are the ones the compiler and engine consume.

## Built-in MCP server

The package ships a basic [MCP](https://modelcontextprotocol.io) server that exposes
these capabilities as agent tools. Once connected, assistants such as VS Code
Copilot Chat can inspect a specification, explain catalog functions, compile
plans, and execute individual calculated features conversationally.

## Build your own MCP server

By looking at the mcp example in source code, it is almost trivial to define your own agentic interface.

## What the server exposes

Vectorize and aggregate functions build Polars expressions inside the
dependency graph, so the meaningful execution unit is a function **bound to
features**, not the raw function. The server therefore offers two layers:

Introspection over the specification:

- `list_functions` — every catalog function id grouped by category
- `describe_function` — one function's entrypoint, declared arguments, and
  resolved Python signature
- `list_calculated_features` — a sorted list of calculated feature ids
- `describe_feature` — one calculated feature's producing function, direct
  dependencies, and full transitive closure split into input and calculated
  features
- `reload_specification` — re-parse the spec after editing it

Execution through the compiler and engine:

- `compile_plan` — compile the full specification or a feature subset and
  report the staged operations
- `execute_feature` — compile the minimal graph producing one calculated
  feature, run it, and return dimension-keyed rows as JSON

## Installation

The server lives in the optional `mcp` extra:

```sh
poetry install --extras "mcp"
```

This installs [FastMCP](https://github.com/jlowin/fastmcp) and registers the
`uptimely-mcp` command. No language model is involved on the server side — MCP
is plain JSON-RPC; the model lives in the client host.

## Running the server

```sh
uptimely-mcp \
  --spec examples/example_1/generated/spec/spec.json \
  --project-root . \
  --runtime-resources examples/example_1/runtime-resources.json
```

The arguments:

Argument | Purpose
--- | ---
`--spec` | Path to the JSON specification. Required.
`--project-root` | Directory added to `sys.path` so function entrypoints resolve. Defaults to the working directory.
`--runtime-resources` | JSON file with values for `?storage`-style placeholders. The example mapping supplies local paths for source datasets.

For dev, test, or prod, pass the corresponding resource file to
`--runtime-resources`. The CLI loads its JSON into the engine's
`runtime_resources` mapping; it does not select an environment or merge files
automatically. Only values referenced by runtime placeholders are substituted,
not arbitrary specification fields. See the
[runtime override guide](../engine/index.md#runtime-overrides) for the file
structure and Python API usage.

The server communicates over stdio and is normally launched by the MCP client,
not by hand. Anything printed to stdout corrupts the protocol channel, so the
server must log to stderr only.

## Connecting VS Code Copilot Chat

The repository contains a ready-made
[`.vscode/mcp.json`](../../../.vscode/mcp.json) for VS Code Copilot Chat. Keep
`.vscode/` at the repository root, not inside `.devcontainer/`. In a Dev
Container window, VS Code resolves `${workspaceFolder}` to the container's
workspace and launches the server from its Poetry virtual environment.

```json
{
  "servers": {
    "uptimely": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/uptimely-mcp",
      "cwd": "${workspaceFolder}",
      "args": [
        "--spec",
        "${workspaceFolder}/examples/example_1/generated/spec/spec.json",
        "--project-root",
        "${workspaceFolder}",
        "--runtime-resources",
        "${workspaceFolder}/examples/example_1/runtime-resources.json"
      ]
    }
  }
}
```

To use it:

1. In the Dev Container, `post-create.sh` installs the MCP extra and exports
   the example specification. Outside the Dev Container, run
   `poetry config virtualenvs.in-project true --local`,
   `poetry install --extras "mcp"`, and
   `poetry run python -m examples.example_1.run_export_spec`.
2. Reopen the folder in the Dev Container if needed, then open Copilot Chat in
   **Agent mode** — tools are not available in Ask mode.
3. Check the tools icon to confirm the `uptimely` tools are listed, then ask
   for example: *"describe the pump_health_score function"* or *"execute
   pump_health_score and show three rows"*.

MCP sampling uses VS Code's default available models. The repository does not
pin an `allowedModels` list because VS Code identifies a workspace MCP server
using a key that includes the local workspace folder name. To customize model
access for this server, use **MCP: List Servers** in the Command Palette.

The Dev Container sets `chat.mcp.autostart` to `newAndOutdated`. When you submit
a chat message, VS Code starts new servers and servers whose configuration has
changed. The existing workspace configuration launches `uptimely` inside the
container using the environment prepared by `post-create.sh`. Rebuild the
container to apply changes to its VS Code settings.

Autostart does not override a disabled server or retry a server in an error
state. If `uptimely` is disabled, enable it once through **MCP: List Servers**;
if it is in an error state, inspect the error and restart it after resolving
the cause. Server trust prompts must also be approved.

The stdio process belongs to the MCP client, not the container lifecycle.
Do not launch it from `post-create.sh` or `postStartCommand`: a separate
background process cannot share its stdio connection with Copilot. Automatic
startup happens through the client, not immediately when the container boots.
Use **MCP: List Servers** in the Command Palette and the **MCP** channel in the
Output panel to inspect status and raw JSON-RPC traffic when troubleshooting.

If startup reports "No such file or directory", check that
`.venv/bin/uptimely-mcp` exists in the container workspace. Run
`poetry install --extras "mcp"` in the container if it is missing. The
Dockerfile already installs Poetry, and `post-create.sh` prepares the virtual
environment; installing Poetry on the local host does not repair the
container environment.

This is VS Code's native configuration (`servers`, with workspace-variable
substitution). Clients that require a root `.mcp.json` with `mcpServers`, such
as some CLI or Agent Host integrations, need their own configuration and
must launch the process in the container. Moving a configuration file alone
does not make a host-side client run inside the Dev Container.

## Example requests

Once connected, an assistant can answer questions that would otherwise require
running the runners by hand:

- *"Which vectorize functions does this specification declare?"* →
  `list_functions`
- *"What arguments does `normalize_health_signal` take?"* → `describe_function`
- *"What does `pump_health_score` depend on?"* → `describe_feature`
- *"Compile a plan for `pump_health_score` and list its stages"* →
  `compile_plan`
- *"Compute `pump_health_score` for five pumps"* → `execute_feature`
- *"I edited the spec; reload it"* → `reload_specification`

`execute_feature` returns entity dimension keys plus the computed feature, so
results stay traceable to the owning entity rather than bare numbers. The
example engine runner also returns the IDs of calculated features directly,
without writing a calculated telemetry output file.

## Limitations

- The server wraps the built-in batch engine; streaming sources are not
  available.
- Subset plans still execute the owning dataset's sinks. A sink that expects
  features outside the subset fails after the calculation succeeds — the tool
  reports such failures under `warnings` while still returning the computed
  rows.
- Frame payloads are capped by the `max_rows` argument of `execute_feature` to
  keep responses within a size agents can handle.
