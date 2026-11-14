# Release 14: Live cooling-pump demo, Spec editing, and MCP chat

This is a planned release grouping, not a published software version.
Work packages remain ordered by their stated prerequisites. They can proceed
independently of the Explorer navigation and lineage changes.

## Work package: Scaleway demo deployment foundation

Prepare a small, measured Scaleway deployment for the live cooling-pump demo.

**Prerequisites:** Existing live Explorer server and project build operations.
This package does not depend on isolated runtime launchers or deployment adapters.

| title | breaking | description |
|---|---|---|
| Measure deployment resource and cost needs | No | Measure startup, build, and sample-run resource use. Check storage, HTTPS, compute, network, and model costs before deployment. |
| Define the hosted application runtime | No | Pin the revision, Python 3.13 or newer, MCP extra, and installed example functions. Use one instance and one application worker initially. |
| Add a project-specific server entrypoint | No | Serve an explicit project with HTTPS plus health and readiness checks. |
| Configure host operations | No | Add a checked-in deployment definition for process supervision, host updates, network access, and backups. |

## Work package: Persistent demo project setup

Seed and serve the example project safely from persistent demo storage.

**Prerequisites:** Scaleway demo deployment foundation.

| title | breaking | description |
|---|---|---|
| Seed the demo project once | No | Create sample data, configuration, and an editable JSON Spec on persistent storage only when absent. |
| Scope demo file access | No | Resolve input and output paths from the project root. Disable the external workflow until its file access is scoped to demo storage. |
| Build before readiness | No | Build the project before reporting the live application ready. |
| Start with read-only demo access | No | Initially expose browsing and saved-run diagnostics only. |

## Work package: Live demo cutover and recovery

Switch users to the verified live demo while preserving edits and a recovery
path.

**Prerequisites:** Persistent demo project setup.

| title | breaking | description |
|---|---|---|
| Preserve edits across restarts and upgrades | No | Back up before rebuilding and report incompatible edits without replacing them. |
| Verify deployment and recovery | No | Test assets, persistence, backup restoration, failed deployment recovery, and sample runs. Document rollback. |
| Cut over demo links | No | After verification, move demo links to the live service and replace the static demo landing page with a live link. Keep documentation on Pages and static export available. Document setup and measured resource costs. |

## Work package: Protected demo Spec editing

**Prerequisites:** Persistent demo project setup.

| title | breaking | description |
|---|---|---|
| Add authenticated Spec editing | No | Provide maintainer UI and APIs for validated JSON Specs. Reject Python source, arbitrary imports, entrypoints, and paths. |
| Preserve the last valid Spec and build | No | Retain the last valid version on build failure and provide explicit errors and reset. |
| Serialize edits and reject stale revisions | No | Serialize edits and builds, reject stale edits with revision tokens, and refresh Explorer and MCP after successful builds. |
| Confirm protected mutations | No | Require confirmation for edits and other mutations. Test permissions, concurrent requests, persistence, and failed-build recovery. |

## Work package: Bounded demo execution

Run only permitted demo calculations without blocking or overloading the live
service.

**Prerequisites:** Protected demo Spec editing.

| title | breaking | description |
|---|---|---|
| Add authorized demo calculation runs | No | Expose only allowed demo calculations and require confirmation before execution. |
| Serialize runs with edits and builds | No | Prevent runs from racing with Spec edits or builds. |
| Run calculations outside request handlers | No | Use bounded queues, timeouts, and cancellation for expensive work. |
| Limit live demo resource use | No | Bound concurrency, requests, and storage. Keep anonymous users read-only until isolated visitor workspaces exist. |
| Verify execution limits and access | No | Test permissions, concurrent runs, cancellation, and resource limits. |

## Work package: Remote MCP access to the live demo

**Prerequisites:** Bounded demo execution.

| title | breaking | description |
|---|---|---|
| Add Streamable HTTP MCP transport | No | Use the SDK-backed transport for the live demo and retain local stdio support. |
| Secure remote MCP access | No | Reuse protected project access, HTTPS, execution limits, authorization discovery, and origin checks. |
| Verify and document remote MCP clients | No | Test supported clients, disabled tools, and build refresh. Explain that clients provide their own models and a hosted Explorer URL alone is not an MCP connection. |

## Work package: MCP chat in Explorer

Let users ask about the current analytics project and run its calculations
without leaving Explorer.

**Prerequisites:** Bounded demo execution and existing Uptimely MCP tools.
Remote MCP access is not required.

| title | breaking | description |
|---|---|---|
| Add Explorer chat and model integration | No | Add a chat panel and server-side tool-calling loop using one configurable hosted model API and an in-process MCP client. |
| Validate and confirm chat tool calls | No | Enforce project permissions, show calls and results, and require confirmation before execution. Report tool failures explicitly. |
| Keep chat on the current build | No | Prevent chat from using a replaced build unnoticed. |
| Bound chat usage | No | Limit tool rounds, tokens, execution time, and retries. Restrict paid chat to authenticated users with per-user quotas and a spending cutoff. |
| Protect model credentials and user data | No | Keep credentials on the server, use sample data, and explain external model data sharing. |
| Verify chat availability and document setup | No | Keep browsing available without a model key or when the provider is unavailable. Explain that chat requires a live server in static exports. Test connection, permissions, provider failures, and limits. Defer local-model hosting and multi-instance deployment. |
