"""Cross-process locking for active build bundles."""

from __future__ import annotations

import contextlib
import os
import pathlib
import typing

from uptimely import project_paths as paths
from uptimely.project.build.errors import BuildLockError

if os.name == "nt":
    import msvcrt
else:
    import fcntl


@contextlib.contextmanager
def build_lock(
    project_root: str | pathlib.Path, *, exclusive: bool, wait: bool = True
) -> typing.Generator[None]:
    """Coordinate bundle reads and writes across builders and consumers.

    Builders should acquire a nonblocking exclusive lock. Consumers acquire a
    lock which may be held for the lifetime of a serving process. On platforms
    with shared file locks, multiple consumers can hold it concurrently.
    """
    project_root = pathlib.Path(project_root).resolve()
    lock_path = project_root / paths.GENERATED_DIR / ".build.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            mode = msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK
            try:
                msvcrt.locking(lock_file.fileno(), mode, 1)
            except OSError as error:
                raise BuildLockError(
                    f"Cannot acquire the active build lock at {lock_path}; another build or "
                    f"consumer may be using the bundle. Stop it or retry when it finishes: "
                    f"{error}"
                ) from error
        else:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            if not wait:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(lock_file.fileno(), operation)
            except OSError as error:
                raise BuildLockError(
                    f"Cannot acquire the active build lock at {lock_path}; another build or "
                    f"consumer may be using the bundle. Stop it or retry when it finishes: "
                    f"{error}"
                ) from error
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
