"""Export the packaged Explorer frontend with a saved data snapshot."""

import json
import pathlib
import shutil
import zipfile

from uptimely import project_paths
from uptimely.explorer import presentation

_BUILD_INSTRUCTION = "Run 'uptimely project build' to generate a valid Explorer snapshot."


def _read_snapshot(project_root: pathlib.Path) -> bytes:
    """Read and validate the snapshot once, preserving its original JSON bytes."""
    snapshot_path = project_root / project_paths.EXPLORER_DATA_FILE
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
        + json.dumps({"dataUrl": "./data/explorer.json"})
        + ");\n"
    )


def export_static(
    project_root: str | pathlib.Path,
    output_path: str | pathlib.Path,
) -> pathlib.Path:
    """Export the static frontend and current snapshot to a directory or ZIP.

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
        ValueError: The snapshot is invalid or output overlaps packaged assets.
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
    files = sorted(path for path in static_root.rglob("*") if path.is_file())
    if output.suffix.lower() == ".zip":
        if output.exists() and output.is_dir():
            raise IsADirectoryError(f"ZIP destination is a directory: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in files:
                relative = source.relative_to(static_root).as_posix()
                content = (
                    _static_config().encode("utf-8")
                    if relative == "config.js"
                    else source.read_bytes()
                )
                archive.writestr(relative, content)
            archive.writestr("data/explorer.json", snapshot)
        return output

    output.mkdir(parents=True, exist_ok=True)
    for source in files:
        relative = source.relative_to(static_root)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.as_posix() == "config.js":
            target.write_text(_static_config(), encoding="utf-8")
        else:
            shutil.copyfile(source, target)
    data_target = output / "data" / "explorer.json"
    data_target.parent.mkdir(parents=True, exist_ok=True)
    data_target.write_bytes(snapshot)
    return output
