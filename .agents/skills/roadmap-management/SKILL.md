---
name: roadmap-management
description: "Manage Uptimely Core roadmap contents in docs/roadmap. Use when reviewing the backlog, removing completed items, adding requested work packages, updating dependencies or ordering, or sizing work for a single pull request."
---

# Roadmap Management

Maintain the roadmap under `docs/roadmap/`, especially
[`backlog.md`](../../../docs/roadmap/backlog.md). Preserve its existing format,
clear wording, and consistency with the project.

## Procedure

1. Read the relevant roadmap pages and inspect repository evidence for any
   completion or dependency claims that affect the requested change.
2. Remove an item from the backlog only when its completion is confirmed by
   merged implementation, tests, or documentation as appropriate. Do not treat
   a plan, partial implementation, or an unmerged change as completed work.
3. Add backlog work only when requested. Put it in a new or existing work
   package according to its dependencies and scope. Keep title, breaking
   status, description, and prerequisites consistent with neighboring entries.
4. Order work packages so prerequisites precede dependents. Name prerequisites
   using the corresponding work package titles, and keep independent work
   schedulable without inventing dependencies. Update references when a package
   is renamed, split, or moved.
5. Keep each work package small enough for one pull request, with a clear
   outcome and bounded implementation, testing, and documentation scope. A
   backlog item can require one or more commits within that package. Split
   broader work into smaller work packages, ordered by their actual
   dependencies. Avoid unrelated work in the same package.
6. Review all affected roadmap pages for stale references, contradictory
   ordering, duplicated items, and completed backlog work.

## Constraints

- Do not implement product changes while managing the roadmap.
- Do not silently drop requested work or weaken its stated outcome.
- Do not claim completion or add prerequisites without evidence.
- Keep roadmap pages focused on planned work; preserve published software
  release terminology when it refers to actual versioning or upstream releases.
