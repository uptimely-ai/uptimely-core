"""Exceptions raised while locating, validating, or publishing active builds."""

from __future__ import annotations

import pathlib
import shlex
import typing


class BuildError(RuntimeError):
    """An actionable failure while locating or validating an active build."""

    def __init__(
        self,
        status: typing.Literal["missing", "incomplete", "invalid"],
        detail: str,
        project_root: pathlib.Path,
    ) -> None:
        """Create a consistently formatted error with a safely quoted recovery command."""
        self.status = status
        self.detail = detail
        self.recovery_command = shlex.join(
            [
                "uptimely",
                "project",
                "build",
                "--project-root",
                str(project_root),
            ]
        )
        descriptions = {
            "missing": "No active build found",
            "incomplete": f"Active build is incomplete: {detail}",
            "invalid": f"Active build is invalid: {detail}",
        }
        action = "Create one" if status == "missing" else "Rebuild it"
        super().__init__(f"{descriptions[status]}. {action} with: {self.recovery_command}")


class ProjectBuildError(RuntimeError):
    """A failure while building or publishing an active bundle."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"Project build {stage} failed: {detail}")


class BuildLockError(RuntimeError):
    """A build cannot acquire the active bundle lock."""
