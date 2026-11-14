"""Manage saved-build and runtime configuration state for the MCP server."""

import dataclasses
import pathlib

from uptimely import project as project_module


@dataclasses.dataclass
class ServerState:
    """Hold project configuration and cache its validated saved build."""

    project: project_module.Project
    bundle: project_module.BuildBundle | None = dataclasses.field(default=None, repr=False)

    @property
    def project_root(self) -> pathlib.Path:
        """Return the configured project root."""
        return self.project.root

    def load_bundle(self, *, reload: bool = False) -> project_module.BuildBundle:
        """Load and cache one validated saved build.

        Args:
            reload: Discard any cached build and read the saved artifacts again.

        Returns:
            The validated bundle and its source model, execution plan, and manifest.
        """
        if self.bundle is not None and not reload:
            return self.bundle
        if reload:
            self.bundle = None

        with self.project.read_build_bundle() as bundle:
            loaded_bundle = bundle
        self.bundle = loaded_bundle
        return loaded_bundle
