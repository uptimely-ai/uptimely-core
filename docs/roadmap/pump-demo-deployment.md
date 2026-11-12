# Pump analytics live demo deployment plan

Move the public pump analytics demo from a static GitHub Pages export to a
live Python server. Keep the documentation site on GitHub Pages. The live demo
will support server-backed features as they are implemented, including Spec
editing, analytical execution, and MCP access.

This is a deployment recommendation, not an implemented service or a promise
that those features already exist.

## Recommended first host

Use **one paid Render Python web service with a persistent disk**. Connect
the GitHub repository, deploy a pinned revision, and serve the existing
FastAPI Explorer through Render's HTTPS address. Start with one instance and
one application worker.

This is the lowest-effort recommendation for the current file-based project:

| Option | Setup and maintenance | Fit for this demo |
| --- | --- | --- |
| Render web service and disk | Git-connected deployment, managed HTTPS, logs, and local persistent storage | Recommended. Closely matches the current Python server and project files. |
| Railway service and volume | Also supports Git-connected FastAPI deployment, with usage-based billing | Reasonable alternative if a Railway workspace already exists. |
| A small VPS | Requires OS updates, HTTPS proxy, process supervision, backups, and deployment setup | Useful later for custom infrastructure or a local model, not the lowest operational effort. |
| GitHub Pages | Static files only | Keep for documentation, not for editing or running analytics. |

Do not use Render's free service for persistent edits. It sleeps after
inactivity, loses local changes on restart, and cannot attach a persistent disk.
The disk is available only at runtime, not during the service build step.
Disk-backed services have deployment downtime and cannot scale to multiple
instances sharing that disk.

Choose the smallest paid instance that passes a startup, build, and sample-run
memory check. The smallest paid plan currently has 512 MB RAM, which must not
be assumed sufficient for this package and its builds. Upgrade if measured
usage requires it. Confirm compute, disk, traffic, and model pricing before
deployment. Do not treat a service's minimum price as a fixed total budget.
Railway's Hobby plan currently starts at $5/month with $5 of included usage,
but resource consumption can exceed that allowance.

## First deployment

1. Install the package and its MCP extra using Python 3.13 or newer. Use
   installed example function modules from the deployed revision, not uploaded
   executable code.
2. Add a small deployment entry point that creates the existing Explorer app
   for an explicit project directory. Bind to `0.0.0.0` and the provider's
   assigned port. Add a health endpoint and a checked-in deployment definition.
3. At runtime, seed a project under a persistent mount such as
   `/var/data/pump-demo` only when it does not exist. Include sample input data,
   runtime configuration, and an editable JSON Spec. Build it with the existing
   Project API before marking the service ready.
4. Point every input and output location at this project. Some current example
   parameters are relative paths, and the external workflow uses module-relative
   paths. Do not assume moving the project automatically moves these resources.
   Disable that uncontrolled workflow in the public demo until its file access
   is explicitly scoped to demo storage.
5. Preserve existing edits on restart and redeploy. Rebuild saved artifacts
   after package or format changes, but never silently replace edited Spec
   declarations. Back up the project before upgrades and document recovery
   when an edited Spec cannot be rebuilt.
6. Deploy browsing and latest-run inspection first. Keep editing, execution,
   and paid chat disabled until their permission and failure handling exist.
7. Verify HTTPS, asset loading, readiness, build and run behavior, restart
   persistence, backup restoration, and deployment failure recovery.
8. Switch README and documentation demo links to the live URL after verification.
   Remove the pump demo export from the Pages workflow and replace its old
   landing page with a link to the live service. Continue publishing MkDocs
   documentation and retain static export as a supported user feature.

Use the provider's default domain initially. A custom domain, database,
container orchestration, and distributed workers are not required.

## Safe Spec editing and execution

Hosting alone does not add Spec editing. The current Explorer serves saved
snapshots and run records, and its API does not expose edit or execution actions.

For the first editable demo, use one shared project with **public read-only
browsing and authenticated maintainer actions**. This avoids implementing
per-visitor storage while preventing visitors from changing everyone else's
demo or triggering unlimited compute.

- Edit a JSON Spec through a bounded UI and validated API. Do not accept Python
  source, arbitrary imports, arbitrary file paths, or unrestricted entrypoints.
  Allow only installed demo functions and data locations.
- Validate a candidate before saving and building it. Keep the previous usable
  Spec and build when validation or compilation fails. Show the actual error.
- Serialize edits, builds, and runs for the shared project. Reject stale edits
  using a revision token, and refresh Explorer and MCP state after a successful
  build. Do not let chat execute against a replaced build unnoticed.
- Run expensive work outside the HTTP request event loop, with a bounded queue,
  timeouts, cancellation, and concurrency limits. Show running and failed states.
- Require authentication and explicit confirmation for mutations and execution.
  Add request limits, storage limits, and an explicit reset-to-example action.
  If anonymous editing is wanted later, first add isolated visitor workspaces.

## MCP and AI: what is actually required?

**MCP is a tool protocol, not an AI model.** The Uptimely server supplies tools
such as listing features or executing an operator. Calling those tools
programmatically requires no model, AI subscription, or model API key.

There are two different ways to add conversational access:

### An existing AI client

VS Code or another AI application provides the model and chat interface.
The application uses its own model configuration or subscription.
The current Uptimely MCP command uses standard input and output, so it cannot
be reached by a remote client just by hosting Explorer at a URL.

Add an authenticated **Streamable HTTP MCP endpoint** for external clients.
Use the existing MCP SDK rather than inventing a protocol. Keep stdio working
for local use. Place the remote endpoint behind the same project permissions,
origin checks, request limits, and HTTPS as the demo. Follow MCP authorization
requirements and test the discovery and authorization flow for supported
clients. Avoid claiming universal client compatibility.

Remote MCP does not require hosting an AI model. The client supplies it.

### Chat inside Explorer

The browser needs a server-side chat controller in addition to the MCP tools:

1. Send the user's question to a configured model together with allowed tool
   descriptions.
2. Validate proposed tool calls and enforce permissions and confirmation.
3. Call Uptimely through an in-process MCP client using the existing SDK.
4. Return tool results to the model and stream the answer to the browser.
5. Bound the number of tool rounds, tokens, execution time, and retries. Display
   tool activity and errors rather than letting the model hide failed actions.

Use a **hosted tool-calling model API first**. Select one provider and one
configurable model for the initial implementation, not a framework supporting
every provider. Store its API key in server secrets, never browser code.
Explain that questions and tool results may leave the server. Use only sample
data, restrict paid chat to authenticated users initially, and enforce usage
quotas and a spending cutoff. Ordinary browsing should still work without a key
or when the model provider is unavailable.

An in-process MCP client can reuse tools without opening a public MCP endpoint.
Consequently, Explorer chat does not depend on remote MCP transport. Both can
be developed after live deployment, and they share permissions and build refresh.

### Local model alternative

A tool-calling model served by Ollama can replace the hosted API for development
or a later private deployment. Ollama still requires the application's
tool-calling loop and permission checks. Tool support depends on the selected
model.

Do not place a local model on the small demo web instance. Model downloads,
memory requirements, CPU latency or GPU hosting, updates, and availability add
operational work. If needed later, run it on a separate adequately sized host
over a private connection, and measure latency and tool-call behavior before
switching. It avoids sending prompts to a hosted model provider, but hardware
and hosting are not free.

## Delivery order

Each item is a separate work package in
[Release 14](release-14-live-demo-mcp.md):

1. **Live pump analytics demo deployment:** browsing, persistence, health checks,
   backup and link migration.
2. **Safe demo Spec editing and execution:** validated mutations and bounded
   runs, protected by maintainer authentication.
3. **Remote MCP access to the live demo:** authenticated HTTP transport for
   external clients.
4. **MCP chat in Explorer:** hosted model integration and the chat panel.
   Remote MCP access is not a prerequisite for this package.

Public anonymous editing, local-model hosting, and multi-instance deployment
are not part of the initial plan.

## Sources

Provider details reviewed on 2026-11-11. Recheck them at implementation time.

- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Render persistent disks and limitations](https://render.com/docs/disks)
- [Render free-service limitations](https://render.com/docs/free)
- [Render compute plans](https://render.com/docs/compute-plans) and
  [pricing](https://render.com/pricing)
- [Railway FastAPI deployment](https://docs.railway.com/guides/fastapi) and
  [pricing](https://railway.com/pricing)
- [MCP architecture and transports](https://modelcontextprotocol.io/docs/learn/architecture)
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
