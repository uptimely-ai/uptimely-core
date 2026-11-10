# Repository agent customizations

Shared, portable repository guidance lives in the root [`AGENTS.md`](../AGENTS.md),
and shared roles, task instructions, and skills live in [`.agents/`](../.agents/).
VS Code-specific customization entry points live here, using the folder names
it discovers:

- [`agents/`](agents/) wraps shared role definitions from
  [`.agents/agents/`](../.agents/agents/).
- [`prompts/`](prompts/) supplies VS Code prompt metadata and references the
  shared task instructions in [`.agents/prompts/`](../.agents/prompts/).

Reusable on-demand workflows remain in [`.agents/skills/`](../.agents/skills/).
This keeps common content in portable locations and system-specific files
focused on discovery and invocation.
