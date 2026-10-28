# Working with AI Agents

Uptimely Core is built from ground up to natively run and manage numerical calculations with AI agents.

AI assistants can explore an analytics project without custom integration code.

Spec is declared in JSON, functions
are catalog entries with typed arguments, and plans are portable — the same
artifacts an agent can read are the ones the compiler and engine consume.

## Built-in MCP server

The package ships a basic [MCP](https://modelcontextprotocol.io) server that exposes
these capabilities as agent tools. Once connected, assistants such as VS Code
Copilot Chat can inspect the saved spec and execution scope, explain catalog
functions, and run the saved plan conversationally.

## Build your own MCP server

By looking at the mcp example in source code, it is almost trivial to define your own agentic interface.

## What the server exposes

Vectorize and collapse functions return dimension-keyed dataframes. Their
actions declare required and produced features, so execution includes the
prerequisites for a function **bound to features**, not just the raw function.
The server therefore offers two layers:

Introspection over the saved spec and build:

- `list_functions` — every catalog function id grouped by category
- `describe_function` — one function's entrypoint, declared arguments, and
  resolved Python signature
- `list_calculated_features` — a sorted list of calculated feature ids
- `describe_feature` — one calculated feature's producing function, direct
  dependencies, and full transitive closure split into input and calculated
  features
- `describe_build` — the Uptimely version and whether the saved plan covers all
  features or a selected feature scope
- `reload_build` — refresh the validated saved bundle, spec, plan, and scope

Execution through the saved plan and engine:

- `execute_build` — run the saved execution plan as-is and return calculated
  dataset outputs as dimension-keyed JSON rows

MCP never compiles or renders. Choose a full or scoped plan with
`uptimely project build` before starting the server; `execute_build` has no
feature-selection input and cannot change that saved scope. To pick up a newer
successful build while the server is running, call `reload_build`.
Execution runs the saved plan's functions, including configured write sinks,
and can therefore cause external side effects.

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
  --project-root examples/pump_analytics \
  --config examples/pump_analytics/config/engine.json
```

The arguments:

Argument | Purpose
--- | ---
`--project-root` | Analytics project root containing the last successful `_generated/build/`. Defaults to the working directory.
`--config` | JSON file with engine settings and `bind` values. The example binding supplies local paths for source datasets.

Build the project first, for example:

```sh
uptimely build examples/pump_analytics
```

The MCP server rejects missing, incomplete, or invalid builds with a recovery
command. It does not fall back to source files or compile a replacement plan.
Edits to the source spec do not change the saved MCP view until a successful
project build is made and the server runs `reload_build`.

For dev, test, or prod, pass the corresponding engine configuration file to
`--config`. The CLI loads the complete configuration as `EngineConfig`,
including backend settings and the `bind` object; it does not select an environment or merge files
automatically. Only values referenced by runtime placeholders are substituted,
not arbitrary spec fields. See the
[runtime override guide](../components/engine.md#runtime-overrides) for the file
structure and Python API usage.

The server communicates over stdio and is normally launched by the MCP client,
not by hand. Anything printed to stdout corrupts the protocol channel, so the
server must log to stderr only.

## Connecting VS Code Copilot Chat

The repository contains a ready-made
[`.vscode/mcp.json`](https://github.com/uptimely-ai/uptimely-core/blob/main/.vscode/mcp.json) for VS Code Copilot Chat. Keep
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
        "--project-root",
        "${workspaceFolder}/examples/pump_analytics",
        "--config",
        "${workspaceFolder}/examples/pump_analytics/config/engine.json"
      ]
    }
  }
}
```

To use it:

1. In the Dev Container, `post-create.sh` installs the MCP extra. Outside the
   Dev Container, run `./scripts/install-mcp.sh` from the repository root to
   install MCP and build the example bundle.
2. Reopen the folder in the Dev Container if needed, then open Copilot Chat in
   **Agent mode** — tools are not available in Ask mode.
3. Check the tools icon to confirm the `uptimely` tools are listed, then ask
   for example: *"describe the pump_health_score function"* or *"run the saved
   build and show three rows per dataset"*.

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
`.venv/bin/uptimely-mcp` exists in the container workspace. Run the
`./scripts/install-mcp.sh` script in the container if it is missing. The
Dockerfile already installs Poetry, and `post-create.sh` prepares the virtual
environment; installing Poetry on the local host does not repair the container
environment.

This is VS Code's native configuration (`servers`, with workspace-variable
substitution). Clients that require a root `.mcp.json` with `mcpServers`, such
as some CLI or Agent Host integrations, need their own configuration and
must launch the process in the container. Moving a configuration file alone
does not make a host-side client run inside the Dev Container.

## Example requests

Once connected, an assistant can answer questions that would otherwise require
running the runners by hand:

- *"Which vectorize functions does this spec document declare?"* →
  `list_functions`
- *"What arguments does `normalize_health_signal` take?"* → `describe_function`
- *"What does `pump_health_score` depend on?"* → `describe_feature`
- *"What feature scope does this build cover?"* → `describe_build`
- *"Run the saved build and show up to five rows per dataset"* →
  `execute_build`
- *"I rebuilt the project; reload the active build"* → `reload_build`

`execute_build` returns entity dimension keys plus the calculated features for
each dataset, so results stay traceable to their owning entity rather than bare
numbers. It runs the plan's configured sinks, which may persist output.

## Limitations

- The server wraps the built-in batch engine; streaming sources are not
  available.
- Scoped plans still execute their configured sinks. A sink that expects
  features outside the selected plan can fail; if all calculated outputs were
  produced, the tool reports sink failures as warnings.
- Each dataset payload is capped by the `max_rows` argument of `execute_build`
  to keep responses within a size agents can handle.
