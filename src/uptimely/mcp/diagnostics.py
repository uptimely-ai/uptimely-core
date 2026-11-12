"""Expose read-only diagnostics for persisted engine runs."""

import typing

import fastmcp

from uptimely.run import store

from . import serialization, state


class RunDiagnostics:
    """Read the latest persisted run without loading or executing a build."""

    def __init__(self, server_state: state.ServerState) -> None:
        """Bind diagnostics to a project.

        Args:
            server_state: State providing the project root for run artifacts.
        """
        self._state = server_state

    def register(self, server: fastmcp.FastMCP) -> None:
        """Register diagnostics tools with an MCP server.

        Args:
            server: MCP server receiving the tool definitions.
        """
        server.tool(self.describe_last_run)
        server.tool(self.read_last_run_logs)

    def describe_last_run(self) -> str:
        """Read the latest persisted run's status, timing, failures, and profiles.

        Includes runs made through the CLI or Python, not only this MCP process.
        """
        manifest = store.RunStore(self._state.project_root).read_manifest()
        return serialization.JsonSerializer.dumps(manifest.model_dump(mode="json"))

    def read_last_run_logs(
        self,
        level: typing.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
        offset: int = 0,
        limit: int = 100,
        run_id: str | None = None,
    ) -> str:
        """Read recorded logs from the latest run without executing anything.

        Args:
            level: Optional exact log level, such as WARNING for logged warnings.
            offset: Nonnegative number of matching events to skip.
            limit: Maximum matching events to return, from 1 to 1,000.
            run_id: Optional token from ``describe_last_run`` to reject a replaced run.
        """
        saved = store.RunStore(self._state.project_root)
        manifest = saved.read_manifest()
        entries = saved.read_logs(
            run_id=manifest.run_id if run_id is None else run_id,
            level=level,
            offset=offset,
            limit=limit,
        )
        return serialization.JsonSerializer.dumps(
            {
                "run_id": manifest.run_id,
                "entries": [entry.model_dump(mode="json") for entry in entries],
                "next_offset": offset + len(entries),
            }
        )
