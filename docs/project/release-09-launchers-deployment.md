# Release 9: Venv and Docker graph launchers with local and Prefect deployment

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Venv whole-graph launcher

Initially run the existing engine as one whole-graph worker job.

**Prerequisites:** Destination bundle preparation.

| title | breaking | description |
|---|---|---|
| Launch bundled graphs in a venv | Yes | Run with the isolated runtime interpreter and bundled implementations, not mutable project modules or developer dependencies. |
| Keep preparation in the parent process | Yes | Limit the parent to runtime preparation and worker launch. |
| Reject unsupported multi-runtime graphs | Yes | Until segmented execution ships, reject graphs requiring multiple runtimes. |
| Preserve whole-graph run behavior | Yes | Preserve result, validation, failure, and diagnostic behavior. |

## Work package: Docker whole-graph launcher

Run the same whole-graph job in a container when OS-level isolation or host
capabilities are required.

**Prerequisites:** Venv whole-graph launcher.

| title | breaking | description |
|---|---|---|
| Build and launch Docker jobs | No | Build from a declared Dockerfile or pinned image and launch the same bundle job with explicit data access and resource configuration. |
| Validate Docker host capabilities | No | Check required capabilities, including GPU host-driver and container compatibility. Distinguish venv dependency isolation from OS/container isolation. |
| Report unsupported placement | No | Report unsupported placement without falling back to the developer process. |

## Work package: Launcher equivalence and documentation

Verify whole-graph launch behavior and explain how to provision each launcher.

**Prerequisites:** Venv whole-graph launcher and Docker whole-graph launcher.

| title | breaking | description |
|---|---|---|
| Verify launcher results and failures | No | Test exit status, worker errors, output collection, immutable source loading, and local venv/Docker result equivalence. |
| Document launcher setup | No | Document provisioning, mounted inputs/outputs, resource needs, and rebuilding after runtime changes. |

## Work package: Bundle deployment adapters

Keep deployment user-defined and independent of analytical declarations.

**Prerequisites:** Launcher equivalence and documentation.

| title | breaking | description |
|---|---|---|
| Define bundle submission inputs and results | No | Place user-owned deployment functions in `deployment/`. Accept an immutable bundle and destination configuration, and return submission identity/status. |
| Keep deployment policy out of the Spec | No | Keep provisioning, placement, resources, secret injection, and orchestration policy in deployment code. |
| Distinguish submission and execution failures | No | Report submission failures separately from worker execution failures. |
| Add local and Prefect deployment examples | No | Deploy the same whole-graph bundle with local-process and Prefect examples. Keep orchestrators from duplicating invocation scheduling. |
| Verify and document deployment adapters | No | Test submission, status, and error propagation. Document the extension pattern without requiring Prefect in every worker runtime. |
