# Shared agent resources

The root [`AGENTS.md`](../AGENTS.md) contains always-on repository guidance.
Shared role definitions live in [`agents/`](agents/), and reusable task
instructions live in [`prompts/`](prompts/). Reusable, on-demand workflows live
in [`skills/`](skills/), which is discovered by agents that support the shared
`.agents/skills/` convention.

System-specific discovery files should reference these shared resources rather
than duplicate their instructions. VS Code agent and prompt entry points live
under [`.github/`](../.github/).
