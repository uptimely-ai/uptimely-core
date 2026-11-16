# App

`Uptimely` is the public-facing API for working with an analytics project. It
binds operations to a project root and provides methods to build, load, or run the
active build bundle. At construction, it loads and validates project
configuration and keeps it for its lifetime. It creates Engines with the
relevant settings, paths, and parameters. The command-line project build and
run use the same project workflow. Its run operation holds the build reader lock
throughout execution and does not rebuild the project.

Internally, `ProjectBuilder` coordinates source discovery and loading,
compilation, artifact generation, validation, and publication. A successful
build produces a `BuildBundle` containing the Spec and portable execution plan.
`BundleStore` reads and validates active or staged bundles. These project
services prepare and manage artifacts; they do not execute the analytics. The
Engine runs a bundle separately.

Use the [Python App API](../reference/python/application.md) for API details and
the [`uptimely build` CLI reference](../reference/cli/project.md) for build
options.

### Publication and locking

The spec, plan, and manifest are generated in a sibling staging directory,
validated, then published in place of the previous bundle. The Explorer
snapshot is serialized before publication and atomically replaces the previous
snapshot only after the build succeeds. A snapshot publication error is reported
explicitly and leaves the previous snapshot intact. Builders coordinate through
a project lock. A build fails rather than publishing while another builder or
cooperating consumer holds the bundle lock. Bundle publication uses rollback if
replacing the directory fails. It does not claim a filesystem-wide atomic
directory swap.
