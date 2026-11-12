---
name: roadmap-management
description: "Manage Uptimely Core roadmap contents in docs/roadmap. Use when reviewing the backlog, removing completed items, adding requested work packages, updating dependencies or ordering, or sizing work for a single pull request."
---

# Roadmap Management

Maintain the roadmap under `docs/roadmap/`, especially
[`index.md`](../../../docs/roadmap/index.md),
[`backlog.md`](../../../docs/roadmap/backlog.md), and the release pages.
Preserve clear wording and consistency with the project.

The index briefly describes future direction. The backlog is the directory of
planned releases, not a list of package descriptions. Each `release-*.md` file
represents one planned release and contains one or more related work packages.
Release numbering indicates planning order only; software version numbers are
assigned when releases are published.

## Procedure

1. Read the index, release directory, affected release pages, and repository
   evidence for any completion or dependency claims that affect the change.
2. Remove an item from the backlog only when its completion is confirmed by
   merged implementation, tests, or documentation as appropriate. Do not treat
   a plan, partial implementation, or an unmerged change as completed work.
3. Add work only when requested. Put it in an existing or new release file
   according to its relationship to other packages and actual prerequisites.
   Keep title, breaking status, description, and prerequisites consistent with
   neighboring entries. Name releases for concrete changes and split unrelated
   packages rather than hiding them under generic capability or foundation labels.
4. Order work packages so prerequisites precede dependents within and across
   release files. Name prerequisites using the corresponding work-package
   titles, and keep independent work schedulable without inventing dependencies.
   Update links and the release directory when a package moves or is renamed.
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
