# MCP API

Connect Uptimely to an MCP-compatible AI application to explore your analytics
project and run calculations. The application provides the chat and model.
The Uptimely server does not need a model API key.

## 1. Install and build

Python 3.13 or newer is required. Install Uptimely and your project's function
dependencies in the same Python environment.

### From an installed package

```sh
python -m pip install --upgrade "uptimely-core[mcp]"
uptimely examples
uptimely build examples/pump_analytics
```

### From this repository

Run from the repository root:

```sh
poetry install --extras "mcp"
poetry run uptimely build examples/pump_analytics
```

Alternatively, run `./scripts/install-mcp.sh`. The Dev Container already
installs the MCP extra, so only the build step is needed there.

## 2. Connect your AI application

The client starts the server and communicates through standard input and
output. No web port or separate background server is needed.

### VS Code in this repository

The checked-in [`.vscode/mcp.json`](https://github.com/uptimely-ai/uptimely-core/blob/main/.vscode/mcp.json)
launches the pump example through Poetry.

1. Open the repository in VS Code, inside the Dev Container if you use one.
2. Run **MCP: List Servers** from the Command Palette.
3. Start **uptimely** and approve its trust prompt.
4. Open an agent chat session and enable the Uptimely tools.
5. Ask: **"Use Uptimely to list the operators in my analytics project."**

If the server is not listed, use **MCP: Add Server** and choose **Command
(stdio)**. Configuration locations vary by VS Code version and session type.
See the [VS Code MCP guide](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

### Other MCP clients or Python environments

Find your Python executable:

```sh
python -c "import sys; print(sys.executable)"
```

In Poetry, prefix this command with `poetry run`.

For clients using an `mcpServers` configuration:

```json
{
  "mcpServers": {
    "uptimely": {
      "command": "/absolute/path/to/python",
      "args": [
        "-m",
        "uptimely.mcp.server",
        "--project-root",
        "/absolute/path/to/examples/pump_analytics"
      ]
    }
  }
}
```

Use your interpreter and project paths. VS Code uses a `servers` root field
instead of `mcpServers`.

Set the client's working directory to the directory containing `examples`
for the pump example. `--project-root` does not change the working directory.
If the client cannot set it, use absolute data paths in the project's
`config/config.json`.

The server reads that configuration by default. An alternative can be supplied
with `--config /path/to/config.json`.

### Containers and remote environments

Launch the server where Python, the project, and its data are available.
Use container paths inside a container and remote paths on a remote machine.
The current server supports local stdio connections, not an HTTP endpoint.

## 3. Ask questions

Start by exploring the model, then ask for the calculation you want:

| Ask | What the assistant can do |
| --- | --- |
| "How many features does my spec have?" | Count features and summarize profiles. |
| "Which calculations are available for pumps?" | List operators, functions, inputs, and outputs. |
| "What does the pump health score depend on?" | Explain its inputs and earlier calculations. |
| "Give me the pump optimization result. Show three rows." | Run optimization and its dependencies. |
| "Run the pressure-flow ratio for the pump telemetry profile." | Run `pressure_flow_efficiency`, which uses the `ratio` function. |
| "Which warnings were logged in the last engine run?" | Read warnings without starting another run. |
| "Which calculation failed in the last run?" | Inspect saved failures and logs. |
| "I rebuilt the project. Reload it and list the calculations." | Refresh the server's saved build. |

When a function is reused, name the profile or operator to select the intended
calculation.

To verify the connection, ask for `describe_spec` and check its returned tool
result. Then request one row from `pressure_flow_efficiency` to check data
access and execution.

For a local startup check:

```sh
python -m uptimely.mcp.server --help
```

Use `poetry run` before this command in a Poetry environment. The command
shows startup options, it does not open a chat.

See the [tool reference](tools.md) for arguments and descriptions of every MCP tool.

## Troubleshooting and limits

| Problem | Action |
| --- | --- |
| Server command cannot be found | Check installation and use the full interpreter path. |
| Tools are missing or disabled | Check server status, trust approval, and enabled tools in the client. |
| Build is missing or incompatible | Build the project, then reload or restart the server. |
| Imports or data files cannot be found | Check function dependencies, working directory, and data paths. |
| No saved run exists | Run a calculation before requesting run diagnostics. |
| Results are not available as rows | The function must return a dataframe through its operator, not only write results internally. |

Restart after changing configuration or server code. Changes to Spec
declarations require a rebuild and reload. Every execution replaces the
latest-run logs and previews, so inspect earlier warnings before starting
another run.

The server does not apply a "today" filter or guarantee data freshness.
The example optimization is a demonstration, not a production optimizer.

Only connect trusted projects. Tools execute project code and may read or write
data. Standard output is reserved for MCP messages, so analytical functions
must not print there. Your AI application may send tool results to its model
provider.

See the [MCP architecture overview](../architecture/ai.md) and
[Engine reference](../architecture/engine.md) for execution behavior.
