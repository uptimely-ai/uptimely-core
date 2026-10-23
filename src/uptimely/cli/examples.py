"""Command-line tools for downloading example projects."""

import argparse
import logging
import pathlib
import re
import shutil
import stat
import tempfile
import zipfile
from http import client
from importlib import metadata
from urllib import error as urllib_error
from urllib import parse, request

logger = logging.getLogger(__name__)

EXAMPLES_FOLDER: str = "examples"
DISTRIBUTION_NAME: str = "uptimely-core"
RELEASE_TAG_PREFIX: str = "v"
EXAMPLES_DOWNLOAD_TIMEOUT: int = 30
TEMPORARY_DIRECTORY_PREFIX: str = ".uptimely-"


def _repository_url() -> str:
    """Read the repository URL from the installed distribution metadata."""
    for entry in metadata.metadata(DISTRIBUTION_NAME).get_all("Project-URL", []):
        label, separator, url = entry.partition(",")
        if separator and label.strip().lower() == "repository":
            return url.strip()
    raise ValueError(f"Installed {DISTRIBUTION_NAME} metadata has no Repository URL")


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


def _ensure_destination_available(output: pathlib.Path) -> None:
    """Fail with recovery guidance when the examples destination already exists."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Examples destination already exists: {output}. Nothing was overwritten. "
            "Choose a different destination with --output PATH, or move/remove the existing "
            "directory and retry."
        )


def download_examples(output: pathlib.Path, ref: str | None = None) -> pathlib.Path:
    """Download the public repository's examples into a new directory.

    Args:
        output: Destination for the contents of the repository's examples directory.
        ref: GitHub branch, tag, or commit. If omitted, use the release tag
            matching the installed package version (v<version>).
            Explicit HEAD selects the default branch.

    Returns:
        Absolute path to the downloaded examples.

    Raises:
        FileExistsError: The destination already exists.
        PackageNotFoundError: The distribution metadata is not installed.
        ValueError: Repository metadata, revision, or archive entries are invalid,
            or the matching release tag is unavailable.
        URLError: GitHub cannot be reached or rejects the download.
        BadZipFile: The downloaded archive is invalid.
        OSError: The files cannot be written.
    """
    output = output.absolute()
    _ensure_destination_available(output)
    revision = f"{RELEASE_TAG_PREFIX}{metadata.version(DISTRIBUTION_NAME)}" if ref is None else ref
    url = _archive_url(_repository_url(), revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=TEMPORARY_DIRECTORY_PREFIX, dir=output.parent
    ) as temporary:
        staging = pathlib.Path(temporary) / "examples"
        staging.mkdir()
        with tempfile.TemporaryFile() as downloaded:
            try:
                with request.urlopen(url, timeout=EXAMPLES_DOWNLOAD_TIMEOUT) as response:
                    shutil.copyfileobj(response, downloaded)
            except urllib_error.HTTPError as error:
                if error.code == 404 and ref is None:
                    raise ValueError(
                        f"Matching examples release tag {revision!r} is unavailable. "
                        "Use --ref to select a revision compatible with your installed package."
                    ) from error
                raise
            downloaded.seek(0)
            with zipfile.ZipFile(downloaded) as archive:
                _extract_examples(archive, staging)
        _ensure_destination_available(output)
        staging.rename(output)
    return output


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the examples command and its download action."""
    parser.set_defaults(
        action="download",
        output=pathlib.Path("examples"),
        ref=None,
    )
    configure_download_parser(parser)
    actions = parser.add_subparsers(dest="action")
    download = actions.add_parser("download", help="Download examples from public GitHub")
    configure_download_parser(download, suppress_defaults=True)


def configure_download_parser(
    parser: argparse.ArgumentParser, *, suppress_defaults: bool = False
) -> None:
    """Configure options for downloading examples."""
    output_default = argparse.SUPPRESS if suppress_defaults else pathlib.Path("examples")
    ref_default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=output_default,
        help="Destination directory (default: examples)",
    )
    parser.add_argument(
        "--ref",
        default=ref_default,
        help="Branch, tag, or commit (default: v<installed package version>)",
    )


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Download examples using parsed command-line arguments."""
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
    logger.info("Downloaded examples to %s", destination)
