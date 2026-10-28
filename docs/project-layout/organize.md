# Organizing analytics projects

This page describes how to organize multiple analytics workflows and their
repositories. For the layout inside one project, see
[analytics project structure](project-structure.md).

## Centralized

Manage related workflows through one shared spec and build bundle in a central
repository. Keep implementations there or distribute shared code as versioned
packages.

For black-box procedures in other repositories or services, keep `escape`
wrappers and their explicit feature dependencies in the central repository.
Wrappers invoke the procedures, wait for required results and report failures.
Use separate `read` mappings to load persisted outputs; side effects do not
automatically create dataframe columns or execution dependencies. See the
[uncontrolled workflow in the pump analytics example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/pump_analytics).

## Clustered

Keep multiple independent workflows in one or multiple repositories.

Each workflow contains its independent spec definition and active build bundle.

Share reusable implementations through packages rather than mixing the workflows'
generated output.

## Decentralized

!!! caution
    Automatic composition of spec documents from multiple repositories is not
    supported. This pattern requires project-specific assembly tooling.

Each repository owns its analytical code and publishes a versioned JSON spec
fragment. A master project combines the fragments into one spec, exposing
cross-repository dependencies through agreed dataset and feature identifiers.
Fragments may reference declarations in other fragments; validate the complete
document after merging and reject conflicting definitions.

Record contributing repositories and artifact versions alongside the assembled
spec, rather than maintaining a hand-edited copy of every team's declarations.
Publishing JSON does not require distributing implementation code, but executing
the combined workflow still requires callable implementations or wrappers.

The master project can keep retrieved fragments in `contributions/`, their
origins and versions in a project-defined `assembly/sources.json`, and the
assembled document in `spec/spec.json`. These are layout conventions, not
built-in discovery paths. Merge source declarations, not generated plans or
build bundles, then build the combined spec as one project.
