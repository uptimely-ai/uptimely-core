"""Manage saved-build and runtime configuration state for the MCP server."""

import dataclasses
import pathlib

from uptimely import engine, project
from uptimely.project import paths


@dataclasses.dataclass
class ServerState:
    """Hold project configuration and cache its validated saved build."""

    project_root: pathlib.Path
    config: engine.Config | None = None
    bundle: project.BuildBundle | None = dataclasses.field(default=None, repr=False)

    @staticmethod
    def load_config(
        config_path: pathlib.Path | None,
        project_root: pathlib.Path,
    ) -> engine.Config:
        """Load runtime configuration from an explicit or project config file.

        Args:
            config_path: Optional path to a JSON configuration file.
            project_root: Project root used to find the default config file.

        Returns:
            Validated runtime configuration, or defaults when no project config exists.
        """
        selected_path = config_path
        if selected_path is None:
            selected_path = project_root / paths.CONFIG_FILE
            if not selected_path.exists():
                return engine.Config()
        return engine.Config.model_validate_json(selected_path.read_text(encoding="utf-8"))

    def runtime_config(self) -> engine.Config:
        """Return the configured engine settings, loading project defaults once."""
        if self.config is None:
            self.config = self.load_config(None, self.project_root)
        return self.config

    def load_bundle(self, *, reload: bool = False) -> project.BuildBundle:
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

        with project.read_build_bundle(self.project_root) as bundle:
            loaded_bundle = bundle
        self.bundle = loaded_bundle
        return loaded_bundle
