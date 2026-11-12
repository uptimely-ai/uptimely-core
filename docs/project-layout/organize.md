# Organizing analytics projects

This page describes how to organize multiple analytics workflows and their
repositories. For the layout inside one project, see
[analytics project structure](project-structure.md).

## Centralized

Organization's full analytical system is in a single project and repository. Simple and clean. Easiest to start and scales quite far, easy to use and access, but might need to be split eventually to multiple projects.

## Clustered

Keep multiple independent Uptimely workflows in one or multiple repositories.

Each workflow contains its independent spec definition and active build bundle.

Share reusable Python code through packages. Keep each workflow’s build bundle and execution results separate.

## Decentralized

!!! caution
    Automatic composition of spec documents from multiple repositories is not natively
    supported. This pattern requires project-specific assembly tooling.

Each repository owns its analytical code and publishes a versioned JSON spec
partial. A master project combines the fragments into one spec, exposing
cross-repository dependencies through agreed profile and feature identifiers.
Fragments may reference declarations in other fragments; validate the complete
document after merging and reject conflicting definitions.

Record contributing repositories and artifact versions alongside the assembled
spec, rather than maintaining a hand-edited copy of every team's declarations.
Publishing JSON does not require distributing implementation code, but executing
the combined workflow still requires callable implementations or wrappers.
