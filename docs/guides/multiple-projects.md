
## Organizing analytics projects

### Centralized

Keep the organization's full analytical system in a single project and
repository. This is simple to start with and keeps analytics easy to find and
access. It can scale far, but may eventually need to be split into multiple
projects.

### Clustered

Keep multiple independent Uptimely workflows in one or more repositories.
Each workflow contains its independent spec definition and active build bundle.

Share reusable Python code through packages. Keep each workflow's build bundle
and execution results separate.

### Decentralized

!!! caution
    Automatic composition of spec documents from multiple repositories is not natively
    supported. This pattern requires project-specific assembly tooling.

Each repository owns its analytical code and publishes a versioned JSON spec
partial. A master project combines the fragments into one spec, exposing
cross-repository dependencies through agreed profile and feature identifiers.
Fragments may reference declarations in other fragments. Validate the complete
document after merging and reject conflicting definitions.

Record contributing repositories and artifact versions alongside the assembled
spec, rather than maintaining a hand-edited copy of every team's declarations.
Publishing JSON does not require distributing implementation code, but executing
the combined workflow still requires callable implementations or wrappers.
