# Project

`Project` is the public-facing API for working with an analytics project. It
binds operations to a project root and provides methods to build or load the
active build bundle. The command-line project build uses the same project
workflow.

Internally, `ProjectBuilder` coordinates source discovery and loading,
compilation, artifact generation, validation, and publication. A successful
build produces a `BuildBundle` containing the Spec and portable execution plan.
`BundleStore` reads and validates active or staged bundles. These project
services prepare and manage artifacts; they do not execute the analytics. The
Engine runs a bundle separately.

Use the [Python Project API](../python/project.md) for API details and the
[project CLI reference](../cli/project.md) for build commands and options.
