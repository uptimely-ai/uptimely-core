"""Export the packaged Explorer frontend with a saved data snapshot."""

import json
import pathlib
import zipfile

from uptimely.explorer import presentation
from uptimely.project import paths
from uptimely.run import store as run_store

_BUILD_INSTRUCTION = "Run 'uptimely project build' to generate a valid Explorer snapshot."
_STATIC_CONFIG_FILE = pathlib.Path("config.js")
_EXPORTED_DATA_FILE = pathlib.Path("data") / "explorer.json"
_EXPORTED_RUN_FILE = pathlib.Path("data") / "run.json"
_LOG_PAGE_SIZE = 1000


def _read_run_snapshot(project_root: pathlib.Path) -> bytes:
    """Validate and combine the latest run for API-free static hosting."""
    runs = run_store.RunStore(project_root)
    try:
        manifest = runs.read_manifest()
    except run_store.RunNotFoundError:
        return b'{"run": null, "logs": [], "previews": {}}\n'

    previews = {
        profile_id: runs.read_preview(profile_id, run_id=manifest.run_id).model_dump(mode="json")
        for profile_id in manifest.profiles
    }
    logs = []
    while True:
        entries = runs.read_logs(run_id=manifest.run_id, offset=len(logs), limit=_LOG_PAGE_SIZE)
        logs.extend(entry.model_dump(mode="json") for entry in entries)
        if len(entries) < _LOG_PAGE_SIZE:
            break
    if runs.read_manifest().run_id != manifest.run_id:
        raise run_store.RunChangedError("The latest run changed. Export the Explorer again.")
    return json.dumps(
        {"run": manifest.model_dump(mode="json"), "logs": logs, "previews": previews},
        allow_nan=False,
    ).encode("utf-8")


def _read_snapshot(project_root: pathlib.Path) -> bytes:
    """Read and validate the snapshot once, preserving its original JSON bytes."""
    snapshot_path = project_root / paths.EXPLORER_DATA_FILE
    try:
        contents = snapshot_path.read_bytes()
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Explorer snapshot is missing. {_BUILD_INSTRUCTION}") from error
    except OSError as error:
        raise OSError(f"Could not read Explorer snapshot: {error}. {_BUILD_INSTRUCTION}") from error

    try:
        data: object = json.loads(contents)
        presentation.validate_presentation_data(data)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(f"Explorer snapshot is invalid: {error}. {_BUILD_INSTRUCTION}") from error
    return contents


def _static_config() -> str:
    """Return a static-host data configuration with a relative URL."""
    return (
        "window.UTIMELY_EXPLORER_CONFIG = Object.freeze("
        + json.dumps({"dataUrl": "./data/explorer.json", "runDataUrl": "./data/run.json"})
        + ");\n"
    )


def _static_asset_content(source: pathlib.Path, relative: pathlib.Path) -> bytes:
    """Return a static asset's export content, replacing its runtime config."""
    if relative == _STATIC_CONFIG_FILE:
        return _static_config().encode("utf-8")
    return source.read_bytes()


def _write_directory_export(
    files: list[pathlib.Path],
    static_root: pathlib.Path,
    output: pathlib.Path,
    snapshot: bytes,
    run_snapshot: bytes,
) -> None:
    """Write frontend assets and the snapshot to an export directory."""
    output.mkdir(parents=True, exist_ok=True)
    for source in files:
        relative = source.relative_to(static_root)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_static_asset_content(source, relative))

    data_target = output / _EXPORTED_DATA_FILE
    data_target.parent.mkdir(parents=True, exist_ok=True)
    data_target.write_bytes(snapshot)
    (output / _EXPORTED_RUN_FILE).write_bytes(run_snapshot)


def _write_zip_export(
    files: list[pathlib.Path],
    static_root: pathlib.Path,
    output: pathlib.Path,
    snapshot: bytes,
    run_snapshot: bytes,
) -> None:
    """Write frontend assets and the snapshot to a ZIP archive."""
    if output.exists() and output.is_dir():
        raise IsADirectoryError(f"ZIP destination is a directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            relative = source.relative_to(static_root)
            archive.writestr(
                relative.as_posix(),
                _static_asset_content(source, relative),
            )
        archive.writestr(_EXPORTED_DATA_FILE.as_posix(), snapshot)
        archive.writestr(_EXPORTED_RUN_FILE.as_posix(), run_snapshot)


def export_static(
    project_root: str | pathlib.Path,
    output_path: str | pathlib.Path,
) -> pathlib.Path:
    """Export the frontend, project snapshot, and latest run to a directory or ZIP.

    A ``.zip`` output path creates an archive. Any other output path is treated
    as a directory; existing files with matching names are replaced.

    Args:
        project_root: Project directory containing the generated snapshot.
        output_path: Destination directory or ZIP file.

    Returns:
        The resolved output path.

    Raises:
        NotADirectoryError: The project root is not a directory.
        FileNotFoundError: The snapshot or packaged frontend is missing.
        ValueError: A snapshot is invalid, the run changes, or output overlaps packaged assets.
        OSError: Reading or writing an export artifact fails.
    """
    root = pathlib.Path(project_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Project directory does not exist: {root}")
    output = pathlib.Path(output_path).expanduser().resolve()
    static_root = pathlib.Path(__file__).parent / "app" / "static"
    if not (static_root / "index.html").is_file():
        raise FileNotFoundError(f"Packaged Explorer frontend is missing: {static_root}")
    if output.is_relative_to(static_root.resolve()):
        raise ValueError("Explorer export destination cannot be inside packaged frontend assets")

    snapshot = _read_snapshot(root)
    run_snapshot = _read_run_snapshot(root)
    files = sorted(path for path in static_root.rglob("*") if path.is_file())
    if output.suffix.lower() == ".zip":
        _write_zip_export(files, static_root, output, snapshot, run_snapshot)
    else:
        _write_directory_export(files, static_root, output, snapshot, run_snapshot)
    return output
