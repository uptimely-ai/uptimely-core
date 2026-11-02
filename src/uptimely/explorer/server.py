"""FastAPI server for generated Analytics Explorer websites."""

import logging
import pathlib

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from uptimely import project_paths

logger = logging.getLogger(__name__)


def create_app(directory: pathlib.Path) -> FastAPI:
    """Create an app that serves the saved Explorer website.

    Args:
        directory: Saved website directory containing an index.html file.

    Returns:
        A FastAPI app serving the website's static files.

    Raises:
        NotADirectoryError: The website directory does not exist or is not a directory.
        FileNotFoundError: The website index is missing.
    """
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Website directory does not exist: {directory}")
    index = directory / project_paths.EXPLORER_INDEX_FILE.name
    if not index.is_file():
        raise FileNotFoundError(
            f"Website index not found: {index}. Generate it with 'uptimely project build'."
        )

    app = FastAPI()
    app.mount("/", StaticFiles(directory=str(directory), html=True), name="explorer")
    return app


def serve_explorer(
    directory: pathlib.Path,
    host: str = "127.0.0.1",
    port: int = 8001,
    scope: str = "all features",
) -> None:
    """Serve a saved analytics explorer website for local preview.

    Args:
        directory: Saved website directory containing an index.html file.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.
        scope: Human-readable scope of the saved execution plan.

    Raises:
        NotADirectoryError: The website directory does not exist or is not a directory.
        FileNotFoundError: The website index is missing.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")

    app = create_app(directory)
    if port:
        logger.info(
            "Serving analytics explorer from %s at http://%s:%d/ (build scope: %s; Ctrl+C to stop)",
            directory.resolve(),
            host,
            port,
            scope,
        )
    else:
        logger.info(
            "Serving analytics explorer from %s (build scope: %s; Ctrl+C to stop)",
            directory.resolve(),
            scope,
        )
    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Spec explorer server stopped.")
        return
    logger.info("Spec explorer server stopped.")
