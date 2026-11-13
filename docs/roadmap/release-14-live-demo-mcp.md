# Release 14: Live cooling-pump demo, Spec editing, and MCP chat

This is a planned release grouping, not a published software version.
Work packages remain ordered by their stated prerequisites. They can proceed
independently of the Explorer navigation and lineage changes.

## Work package: Live data-center cooling pump demo deployment

Move the data-center cooling pump example to a managed Python server rather
than GitHub Pages. Keep the documentation site on Pages. Use one paid Render
web service with a persistent disk as the initial recommendation. See the
[deployment and AI plan](data-center-cooling-pump-demo-deployment.md) for alternatives and rollout.

**Prerequisites:** Existing live Explorer server and project build operations.
This package does not depend on isolated runtime launchers or deployment adapters.

| title | breaking | description |
|---|---|---|
| Deploy the live data-center cooling pump example | No | Add a reproducible server deployment with runtime project seeding, persistent demo data and generated files, health checks, and backup recovery. Verify restart and upgrade behavior without overwriting edits. Initially expose browsing and saved-run diagnostics only. After verification, move public demo links and replace the static demo landing page with a live-service link, keeping documentation on GitHub Pages. Document host setup, resource measurements, operating costs, and rollback. |

## Work package: Safe demo Spec editing and execution

**Prerequisites:** Live data-center cooling pump demo deployment.

| title | breaking | description |
|---|---|---|
| Add protected Spec editing and analytical runs | No | Add authenticated maintainer UI and APIs to edit a validated JSON Spec and run allowed demo calculations. Restrict functions and data paths, retain the last valid build on failure, serialize project work, reject stale edits, refresh Explorer and MCP after successful builds, and provide explicit errors and reset. Bound execution and storage. Test permissions, concurrent requests, persistence, and failed build recovery. Keep anonymous users read-only until isolated visitor workspaces exist. |

## Work package: Remote MCP access to the live demo

**Prerequisites:** Safe demo Spec editing and execution.

| title | breaking | description |
|---|---|---|
| Expose authenticated HTTP MCP tools | No | Add SDK-backed Streamable HTTP transport to the live demo while retaining local stdio support. Reuse protected project access and execution limits. Test supported external clients, authorization discovery, origin checks, disabled tools, and build refresh. Document that clients provide their own AI models and that a hosted Explorer URL alone is not an MCP connection. |

## Work package: MCP chat in Explorer

Let users ask about the current analytics project and run its calculations
without leaving Explorer.

**Prerequisites:** Safe demo Spec editing and execution, and existing Uptimely
MCP tools. Remote MCP access is not required.

| title | breaking | description |
|---|---|---|
| Add MCP chat to Explorer | No | Add a chat panel and server-side tool-calling loop using one configurable hosted model API and an in-process MCP client. Reuse existing tools and protected project actions. Show tool calls, results, and failures, and require confirmation before execution. Keep credentials on the server, explain model data sharing, and enforce per-user quotas and a spending cutoff. Keep browsing functional without a model key. Static exports explain that chat requires a live server. Include connection, permission, provider failure, and limit tests and document setup. Defer local-model hosting, following the deployment and AI plan. |
