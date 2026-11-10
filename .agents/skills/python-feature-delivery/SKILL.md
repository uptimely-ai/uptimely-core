---
name: python-feature-delivery
description: "Implement or debug a Python package feature or bug in Uptimely Core. Use for source changes, tests, type-safe refactoring, and related documentation."
---

# Python feature delivery

Use this workflow for implementation tasks in Uptimely Core. Follow the root
[`AGENTS.md`](../../../AGENTS.md) and
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md).

## Procedure

1. Read the affected implementation, tests, public exports, and nearby docs.
   Trace the behavior through the owning layer before choosing where to change
   it.
2. Search for existing helpers and patterns. Identify compatibility or
   serialized-format implications before changing public behavior.
3. Implement a focused, typed change. Keep validation and error reporting
   explicit, and preserve behavior outside the requested scope.
4. Add or update tests for the requested behavior, including relevant failure
   cases. Update documentation and the Unreleased changelog when user-visible
   behavior changes.
5. Run the smallest relevant test or lint command through Poetry. For
   substantial package changes, run the unit test suite.
6. Review the diff for unrelated edits and report what changed, what checks
   ran, and any remaining limitations.
