"""Publish and read the latest-run snapshot without locking."""

from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import tempfile
import typing
import urllib.parse
import uuid

from uptimely.project import paths as project_paths

from . import models


class RunChangedError(ValueError):
    """The requested run was replaced; consumers must reload the manifest."""


class RunNotFoundError(FileNotFoundError):
    """No latest-run manifest has been saved yet."""


class RunStore:
    """Store the latest run without coordinating concurrent readers or writers."""

    def __init__(self, project_root: pathlib.Path) -> None:
        """Locate the generated run snapshot beneath an analytics project."""
        self.root = project_root.resolve() / project_paths.RUN_OUTPUT_DIR

    @staticmethod
    def preview_path(profile_id: str) -> str:
        """Encode profile IDs as filenames without permitting path traversal."""
        return f"preview/{urllib.parse.quote(profile_id, safe='')}.json"

    def publish(self, staging_root: pathlib.Path) -> None:
        """Replace the entire snapshot, restoring it if promotion fails.

        Args:
            staging_root: Complete staged snapshot on the same filesystem.

        Raises:
            OSError: Publication, restoration, or cleanup fails.
        """
        backup = self.root.parent / f".run-backup-{uuid.uuid4().hex}"
        if self.root.is_symlink() or (self.root.exists() and not self.root.is_dir()):
            raise OSError(f"Latest-run path must be a directory, not a file or link: {self.root}")
        had_previous = self.root.exists()
        if had_previous:
            os.replace(self.root, backup)
        try:
            os.replace(staging_root, self.root)
        except OSError as error:
            if had_previous:
                try:
                    os.replace(backup, self.root)
                except OSError as restore_error:
                    raise OSError(
                        f"Run publication failed: {error}; could not restore the previous "
                        f"run from {backup}: {restore_error}"
                    ) from restore_error
            raise
        if had_previous:
            shutil.rmtree(backup)

    def _artifact(self, relative_path: str) -> pathlib.Path:
        if self.root.is_symlink():
            raise ValueError(f"Latest-run directory must not be a symlink: {self.root}")
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Run artifact escapes its snapshot: {relative_path!r}")
        return path

    def _manifest(self, run_id: str | None = None) -> models.RunManifest:
        try:
            content = self._artifact(models.MANIFEST_FILE).read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise RunNotFoundError("No saved run. Execute 'uptimely run' first.") from error
        manifest = models.RunManifest.model_validate_json(content)
        if run_id is not None and run_id != manifest.run_id:
            raise RunChangedError("The latest run changed. Reload the run manifest.")
        return manifest

    def read_manifest(self) -> models.RunManifest:
        """Read and validate the latest manifest without caching it.

        Raises:
            RunNotFoundError: No saved run is available.
            ValueError: The manifest is invalid.
            OSError: The manifest cannot be read.
        """
        return self._manifest()

    def read_preview(self, profile_id: str, *, run_id: str | None = None) -> models.ProfilePreview:
        """Read and validate an indexed preview.

        Args:
            profile_id: Profile key from the manifest's preview index.
            run_id: Optional consistency token from a previously read manifest.

        Returns:
            The profile's schema and bounded rows, or an explicit failed preview.

        Raises:
            RunNotFoundError: No saved run is available.
            RunChangedError: A different run has replaced the requested snapshot.
            KeyError: The profile has no preview in this run.
            ValueError: The preview is invalid or disagrees with the manifest.
            OSError: An artifact cannot be read.
        """
        manifest = self._manifest(run_id)
        if profile_id not in manifest.profiles:
            raise KeyError(f"No preview for profile {profile_id!r}")
        summary = manifest.profiles[profile_id]
        if summary.preview_path != self.preview_path(profile_id):
            raise ValueError(f"Invalid preview path for profile {profile_id!r}")
        preview = models.ProfilePreview.model_validate_json(
            self._artifact(summary.preview_path).read_text(encoding="utf-8")
        )
        if (
            preview.profile_id != profile_id
            or preview.status != summary.preview_status
            or preview.requested_rows != manifest.preview_rows
            or preview.error != summary.preview_error
            or (preview.status == "succeeded" and len(preview.columns) != summary.column_count)
        ):
            raise ValueError(f"Preview does not match the manifest for {profile_id!r}")
        return preview

    def read_logs(
        self, *, run_id: str | None = None, offset: int = 0, limit: int = 1000
    ) -> list[models.LogEntry]:
        """Read a bounded page of validated JSONL events.

        Args:
            run_id: Optional consistency token from a previously read manifest.
            offset: Nonnegative number of log entries to skip.
            limit: Maximum number of entries to return, between 1 and 1,000.

        Returns:
            Events in emission order; an empty list after the end of the log.

        Raises:
            RunNotFoundError: No saved run is available.
            RunChangedError: A different run has replaced the requested snapshot.
            ValueError: Pagination arguments or log entries are invalid.
            OSError: An artifact cannot be read.
        """
        if offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("Log offset must be nonnegative and limit must be between 1 and 1000")
        manifest = self._manifest(run_id)
        with self._artifact(manifest.log_path).open(encoding="utf-8") as stream:
            entries: list[models.LogEntry] = []
            for index, line in enumerate(stream):
                if index < offset:
                    continue
                entries.append(models.LogEntry.model_validate_json(line))
                if len(entries) == limit:
                    break
            return entries

    @contextlib.contextmanager
    def staging(self) -> typing.Generator[pathlib.Path]:
        """Create and clean up a private staging directory beside the latest run."""
        self.root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".run-staging-", dir=self.root.parent) as directory:
            yield pathlib.Path(directory)
