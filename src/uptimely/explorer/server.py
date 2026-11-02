"""FastAPI server for the packaged Analytics Explorer frontend."""

import json
import logging
import pathlib
import shutil
import tempfile

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from uptimely import project_paths
from uptimely.explorer import export as explorer_export
from uptimely.explorer import presentation

logger = logging.getLogger(__name__)
_BUILD_INSTRUCTION = "Run 'uptimely project build' to generate a valid Explorer snapshot."


def _read_snapshot(path: pathlib.Path) -> Response:
    """Read and validate the Explorer snapshot without caching it in the app."""
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503, detail=f"Explorer data is missing. {_BUILD_INSTRUCTION}"
        ) from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"Explorer data could not be read: {error}. {_BUILD_INSTRUCTION}",
        ) from error

    try:
        content = presentation.serialize_presentation_data(
            presentation.validate_presentation_data(data)
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"Explorer data is invalid or unsupported: {error}. {_BUILD_INSTRUCTION}",
        ) from error
    return Response(content, media_type="application/json", headers={"Cache-Control": "no-store"})


def create_app(project_root: pathlib.Path) -> FastAPI:
    """Create an app serving packaged frontend files and the current data snapshot.

    Args:
        project_root: Project directory containing ``_generated/explorer.json``.

    Returns:
        A FastAPI app serving the packaged frontend and Explorer data API.

    Raises:
        NotADirectoryError: The project root does not exist or is not a directory.
        FileNotFoundError: Packaged frontend assets are unavailable.
    """
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(f"Project directory does not exist: {project_root}")

    static_root = pathlib.Path(__file__).parent / "app" / "static"
    if not (static_root / "index.html").is_file():
        raise FileNotFoundError(f"Packaged Explorer frontend is missing: {static_root}")

    app = FastAPI()

    @app.get("/api/explorer", include_in_schema=False)
    def explorer_data() -> Response:
        return _read_snapshot(project_root / project_paths.EXPLORER_DATA_FILE)

    @app.get("/api/explorer/export", include_in_schema=False)
    def export_explorer() -> FileResponse:
        temporary_root = pathlib.Path(tempfile.mkdtemp(prefix="uptimely-explorer-export-"))
        archive = temporary_root / "uptimely-explorer.zip"
        try:
            explorer_export.export_static(project_root, archive)
        except (
            FileNotFoundError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            shutil.rmtree(temporary_root)
            raise HTTPException(
                status_code=503,
                detail=f"Explorer export failed: {error}. {_BUILD_INSTRUCTION}",
            ) from error
        except OSError as error:
            shutil.rmtree(temporary_root)
            raise HTTPException(
                status_code=500, detail=f"Explorer export failed: {error}"
            ) from error
        return FileResponse(
            archive,
            filename=archive.name,
            media_type="application/zip",
            background=BackgroundTask(shutil.rmtree, temporary_root),
        )

    app.mount("/", StaticFiles(directory=str(static_root), html=True), name="explorer")
    return app


def serve_explorer(
    project_root: pathlib.Path,
    host: str = "127.0.0.1",
    port: int = 8001,
    scope: str = "all features",
) -> None:
    """Serve the packaged Explorer frontend for local preview.

    Args:
        project_root: Project directory containing the generated snapshot.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.
        scope: Human-readable scope of the saved execution plan.

    Raises:
        NotADirectoryError: The project root does not exist or is not a directory.
        FileNotFoundError: Packaged frontend assets are unavailable.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")

    app = create_app(project_root)
    if port:
        logger.info(
            "Serving analytics explorer from %s at http://%s:%d/ (build scope: %s; Ctrl+C to stop)",
            project_root.resolve(),
            host,
            port,
            scope,
        )
    else:
        logger.info(
            "Serving analytics explorer from %s (build scope: %s; Ctrl+C to stop)",
            project_root.resolve(),
            scope,
        )
    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Spec explorer server stopped.")
        return
    logger.info("Spec explorer server stopped.")
