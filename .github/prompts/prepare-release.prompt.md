---
name: Prepare release
description: "Prepare Uptimely Core release metadata, changelog entries, and verified backlog cleanup."
argument-hint: "Specify stable or development release and target version, if known"
agent: developer
---

Prepare the requested release: **${input:request}**

Follow the shared task instructions in
[`.agents/prompts/prepare-release.md`](../../.agents/prompts/prepare-release.md)
and use the `release-preparation` skill.
