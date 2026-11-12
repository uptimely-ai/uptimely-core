# Release 9: Venv and Docker graph launchers with local and Prefect deployment

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Whole-graph isolated runtime launchers

Initially launch the existing engine as one whole-graph worker job rather
than introducing distributed scheduling.

**Prerequisites:** Portable ZIP execution bundles.

| title | breaking | description |
|---|---|---|
| Launch a whole graph in a venv process | Yes | Run the bundled graph using its isolated runtime interpreter and bundled implementations, not mutable project modules or developer dependencies. Keep the parent process responsible for preparation and launch only. Until segmented execution ships, reject graphs requiring multiple runtimes explicitly. Preserve existing result, validation, failure, and diagnostic behavior. |
| Add a Docker launcher using the same job contract | No | Build from a declared Dockerfile or use a pinned image reference, then launch the same bundle job with explicit data access and resource configuration. Validate required capabilities, including GPU host-driver and container compatibility. Distinguish venv dependency isolation from OS/container isolation, and report unsupported placement without falling back to the developer process. |
| Verify launcher equivalence | No | Test process exit status, worker errors, output collection, immutable source loading, and local venv/Docker result equivalence on supported fixtures. Document provisioning commands, mounted input/output locations, resource requirements, and rebuilding after runtime changes. |

## Work package: Bundle deployment adapters

Keep deployment user-defined and independent of analytical declarations.

**Prerequisites:** Whole-graph isolated runtime launchers.

| title | breaking | description |
|---|---|---|
| Define a deployment submission contract | No | Place user-owned deployment functions in `deployment/`. Accept an immutable bundle plus destination configuration and return submission identity/status rather than assuming synchronous completion. Keep provisioning, placement, resources, secret injection, and orchestration policy here, outside the Spec. Surface submission and execution failures distinctly. |
| Demonstrate local and Prefect deployment | No | Provide local-process and Prefect examples that deploy the same whole-graph bundle, with a contract reusable by other orchestrators. Initially orchestrators launch one engine job rather than duplicating invocation scheduling. Test submission, status, and error propagation with adapter fixtures and document the extension pattern without requiring Prefect in every worker runtime. |
