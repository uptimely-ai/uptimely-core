# Release 14: Live cooling-pump demo, Spec editing, and MCP chat

This is a planned release grouping, not a published software version.
Work packages remain ordered by their stated prerequisites. They can proceed
independently of the Explorer navigation and lineage changes.

## Work package: Live data-center cooling pump demo deployment

Move the data-center cooling pump example to a Scaleway-hosted Python server
rather than GitHub Pages. Keep the documentation site on Pages. Use a single
instance, one application worker, persistent storage, and HTTPS initially.
Size it from measured startup, build, and sample-run resource usage, and check
the storage and HTTPS setup and compute, storage, network, and model costs
before deployment.

**Prerequisites:** Existing live Explorer server and project build operations.
This package does not depend on isolated runtime launchers or deployment adapters.

| title | breaking | description |
|---|---|---|
| Deploy the live data-center cooling pump example | No | Deploy a pinned revision with Python 3.13 or newer, the MCP extra, and installed example functions on Scaleway. Provide a server entry point for an explicit project, HTTPS, health and readiness checks, and a checked-in deployment definition. Configure process supervision, host updates, network access, and backups. Seed sample data, configuration, and an editable JSON Spec on persistent storage only when absent, and build before readiness. Resolve input and output paths from the project root and disable the external workflow until its file access is scoped to demo storage. Preserve edits through restarts and upgrades, back up before rebuilding, and report incompatible edits without replacing them. Initially expose browsing and saved-run diagnostics only. Verify asset loading, persistence, backup restoration, failed deployment recovery, and sample runs. After verification, move demo links and replace the static demo landing page with a live-service link while keeping documentation on GitHub Pages and static export available to users. Document Scaleway setup, resource measurements, costs, and rollback. |

## Work package: Safe demo Spec editing and execution

**Prerequisites:** Live data-center cooling pump demo deployment.

| title | breaking | description |
|---|---|---|
| Add protected Spec editing and analytical runs | No | Add authenticated maintainer UI and APIs to edit a validated JSON Spec and run allowed demo calculations. Reject Python source, arbitrary imports, entrypoints, and paths. Retain the last valid Spec and build on failure, serialize edits, builds, and runs, reject stale edits with revision tokens, refresh Explorer and MCP after successful builds, and provide explicit errors and reset. Require confirmation for mutations and execution. Run expensive work outside the request event loop with bounded queues, timeouts, cancellation, and concurrency, and limit requests and storage. Test permissions, concurrent requests, persistence, and failed build recovery. Keep anonymous users read-only until isolated visitor workspaces exist. |

## Work package: Remote MCP access to the live demo

**Prerequisites:** Safe demo Spec editing and execution.

| title | breaking | description |
|---|---|---|
| Expose authenticated HTTP MCP tools | No | Add SDK-backed Streamable HTTP transport to the live demo while retaining local stdio support. Reuse protected project access, HTTPS, and execution limits. Test supported external clients, authorization discovery, origin checks, disabled tools, and build refresh. Document that clients provide their own AI models and that a hosted Explorer URL alone is not an MCP connection. |

## Work package: MCP chat in Explorer

Let users ask about the current analytics project and run its calculations
without leaving Explorer.

**Prerequisites:** Safe demo Spec editing and execution, and existing Uptimely
MCP tools. Remote MCP access is not required.

| title | breaking | description |
|---|---|---|
| Add MCP chat to Explorer | No | Add a chat panel and server-side tool-calling loop using one configurable hosted model API and an in-process MCP client. Validate proposed calls, enforce project permissions, and show tool calls, results, and failures. Require confirmation before execution and prevent chat from using a replaced build unnoticed. Bound tool rounds, tokens, execution time, and retries. Keep credentials on the server, explain external model data sharing, use sample data, and restrict paid chat to authenticated users with per-user quotas and a spending cutoff. Keep browsing functional without a model key or when the provider is unavailable. Static exports explain that chat requires a live server. Include connection, permission, provider failure, and limit tests and document setup. Defer local-model hosting and multi-instance deployment. |
