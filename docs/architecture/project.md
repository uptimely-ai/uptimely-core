# Project

`Uptimely` is the public-facing API for working with an analytics project. It
binds operations to a project root and provides methods to build, load, or run the
active build bundle. At construction, it loads and validates project
configuration and keeps it for its lifetime. It creates Engines with the
relevant settings, paths, and parameters. The command-line project build and
run use the same project workflow. Its run operation holds the build reader lock throughout execution
and does not rebuild the project.

Internally, `ProjectBuilder` coordinates source discovery and loading,
compilation, artifact generation, validation, and publication. A successful
build produces a `BuildBundle` containing the Spec and portable execution plan.
`BundleStore` reads and validates active or staged bundles. These project
services prepare and manage artifacts; they do not execute the analytics. The
Engine runs a bundle separately.

Use the [Python Project API](../reference/python/project.md) for API details and the
[project CLI reference](../reference/cli/project.md) for build commands and options.
