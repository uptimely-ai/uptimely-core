"""Command-line tools for working with Uptimely."""

import argparse
import functools
import pathlib
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from http import client
from http import server as http_server
from importlib import metadata
from urllib import error as urllib_error
from urllib import parse, request

import jinja2

from uptimely import spec as spec_module
from uptimely.docs import docs as docs_module

EXAMPLES_FOLDER: str = "examples"


def _repository_url() -> str:
    """Read the repository URL from the installed distribution metadata."""
    for entry in metadata.metadata("uptimely-core").get_all("Project-URL", []):
        label, separator, url = entry.partition(",")
        if separator and label.strip().lower() == "repository":
            return url.strip()
    raise ValueError("Installed uptimely-core metadata has no Repository URL")


def _archive_url(repository: str, ref: str) -> str:
    """Build a GitHub archive URL for a repository and revision."""
    parsed = parse.urlsplit(repository)
    match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        raise ValueError(f"Expected a public HTTPS GitHub repository URL, got {repository!r}")
    if not ref.strip():
        raise ValueError("The Git revision must not be empty")
    owner, name = match.groups()
    return f"https://codeload.github.com/{owner}/{name}/zip/{parse.quote(ref, safe='')}"


def _extract_examples(archive: zipfile.ZipFile, destination: pathlib.Path) -> None:
    """Copy regular files under EXAMPLES_FOLDER relative to the repository root."""
    source_parts = EXAMPLES_FOLDER.split("/")
    prefix_length = 1 + len(source_parts)
    copied = False
    for member in archive.infolist():
        if member.is_dir():
            continue
        parts = member.filename.split("/")
        if parts[1:prefix_length] != source_parts:
            continue
        if (
            not parts[0]
            or any(part in {".", ".."} for part in parts)
            or any(not part for part in parts[:-1])
            or "\\" in member.filename
        ):
            raise ValueError(f"Unsafe example archive path: {member.filename!r}")
        file_type = stat.S_IFMT(member.external_attr >> 16)
        if file_type not in {0, stat.S_IFREG}:
            raise ValueError(f"Unsupported example archive entry: {member.filename!r}")
        target = destination.joinpath(*parts[prefix_length:])
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("xb") as output:
            shutil.copyfileobj(source, output)
        copied = True
    if not copied:
        raise ValueError("The repository archive contains no example files")


def download_examples(output: pathlib.Path, ref: str = "HEAD") -> pathlib.Path:
    """Download the public repository's examples into a new directory.

    Args:
        output: Destination for the contents of the repository's examples directory.
        ref: GitHub branch, tag, or commit. HEAD selects the default branch.

    Returns:
        Absolute path to the downloaded examples.

    Raises:
        FileExistsError: The destination already exists.
        PackageNotFoundError: The distribution metadata is not installed.
        ValueError: Repository metadata, revision, or archive entries are invalid.
        URLError: GitHub cannot be reached or rejects the download.
        BadZipFile: The downloaded archive is invalid.
        OSError: The files cannot be written.
    """
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Destination already exists: {output}")
    url = _archive_url(_repository_url(), ref)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".uptimely-", dir=output.parent) as temporary:
        staging = pathlib.Path(temporary) / "examples"
        staging.mkdir()
        with tempfile.TemporaryFile() as downloaded:
            with request.urlopen(url, timeout=30) as response:
                shutil.copyfileobj(response, downloaded)
            downloaded.seek(0)
            with zipfile.ZipFile(downloaded) as archive:
                _extract_examples(archive, staging)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"Destination already exists: {output}")
        staging.rename(output)
    return output


def generate_docs(
    spec: pathlib.Path,
    output: pathlib.Path,
    project_root: pathlib.Path,
    include_generated_at: bool = False,
) -> pathlib.Path:
    """Generate the static analytics documentation website.

    Args:
        spec: Path to the JSON specification.
        output: Directory for the website index and report pages.
        project_root: Directory added to the import path for function entrypoints.
        include_generated_at: Include a timestamp on the specification page.

    Returns:
        The path to the website index.
    """
    root = str(project_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    specification = spec_module.Specification.from_json(spec)
    return docs_module.Documentation(specification).create_html(
        output / "index.html", include_generated_at=include_generated_at
    )


def serve_docs(directory: pathlib.Path, host: str = "127.0.0.1", port: int = 8001) -> None:
    """Serve an existing documentation website for local preview.

    Args:
        directory: Website directory containing an index.html file.
        host: Address to bind; defaults to localhost.
        port: TCP port; defaults to 8001. Zero selects an available port.

    Raises:
        NotADirectoryError: The website directory does not exist or is not a directory.
        FileNotFoundError: The website index is missing.
        ValueError: The port is outside the valid TCP range.
        OSError: The server cannot bind to the requested address.
    """
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Website directory does not exist: {directory}")
    if not (directory / "index.html").is_file():
        raise FileNotFoundError(
            f"Website index not found: {directory / 'index.html'}. "
            "Run 'uptimely docs generate' first."
        )
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    handler = functools.partial(http_server.SimpleHTTPRequestHandler, directory=str(directory))
    with http_server.ThreadingHTTPServer((host, port), handler) as server:
        print(
            f"Serving documentation from {directory} at "
            f"http://{host}:{server.server_port}/ (Ctrl+C to stop)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDocumentation server stopped.")


def _port(value: str) -> int:
    """Parse a valid TCP port for the CLI."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be an integer.") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 0 and 65535.")
    return port


def main() -> None:
    """Run the Uptimely command-line interface."""
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples = commands.add_parser("examples", help="Manage example projects")
    actions = examples.add_subparsers(dest="action", required=True)
    download = actions.add_parser("download", help="Download examples from public GitHub")
    download.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("examples"),
        help="Destination directory (default: examples)",
    )
    download.add_argument(
        "--ref",
        default="HEAD",
        help="Branch, tag, or commit (default: the repository's default branch)",
    )
    docs = commands.add_parser("docs", help="Manage analytics documentation")
    doc_actions = docs.add_subparsers(dest="action", required=True)
    generate = doc_actions.add_parser(
        "generate", help="Generate the specification, feature graph, and execution plan website"
    )
    generate.add_argument(
        "--spec", type=pathlib.Path, required=True, help="JSON specification path"
    )
    generate.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("_generated/docs"),
        help="Website directory (default: _generated/docs)",
    )
    generate.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Root for importing function entrypoints (default: working directory)",
    )
    generate.add_argument(
        "--include-generated-at",
        action="store_true",
        help="Include a build timestamp on the specification page",
    )
    serve = doc_actions.add_parser("serve", help="Serve the generated website for local preview")
    serve.add_argument(
        "--directory",
        type=pathlib.Path,
        default=pathlib.Path("_generated/docs"),
        help="Website directory (default: _generated/docs)",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve.add_argument(
        "--port", type=_port, default=8001, help="TCP port (default: 8001; 0 selects a free port)"
    )
    args = parser.parse_args()
    if args.command == "docs" and args.action == "serve":
        try:
            serve_docs(args.directory, args.host, args.port)
        except (OSError, ValueError) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        return
    if args.command == "docs":
        try:
            index = generate_docs(
                args.spec, args.output, args.project_root, args.include_generated_at
            )
        except (
            OSError,
            ValueError,
            ImportError,
            AttributeError,
            TypeError,
            jinja2.TemplateError,
        ) as error:
            parser.exit(1, f"uptimely: error: {error}\n")
        print(f"Documentation website generated at {index}")
        return
    try:
        destination = download_examples(args.output, args.ref)
    except (
        OSError,
        urllib_error.URLError,
        client.HTTPException,
        zipfile.BadZipFile,
        ValueError,
        metadata.PackageNotFoundError,
    ) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    print(f"Downloaded examples to {destination}")


if __name__ == "__main__":
    main()
