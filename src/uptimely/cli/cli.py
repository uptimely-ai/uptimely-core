"""Command-line tools for working with Uptimely."""

import argparse
import re
import shutil
import stat
from http.client import HTTPException
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

EXAMPLES_FOLDER: str = "examples"


def _repository_url() -> str:
    """Read the repository URL from the installed distribution metadata."""
    for entry in metadata("uptimely-core").get_all("Project-URL", []):
        label, separator, url = entry.partition(",")
        if separator and label.strip().lower() == "repository":
            return url.strip()
    raise ValueError("Installed uptimely-core metadata has no Repository URL")


def _archive_url(repository: str, ref: str) -> str:
    """Build a GitHub archive URL for a repository and revision."""
    parsed = urlsplit(repository)
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
    return f"https://codeload.github.com/{owner}/{name}/zip/{quote(ref, safe='')}"


def _extract_examples(archive: ZipFile, destination: Path) -> None:
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


def download_examples(output: Path, ref: str = "HEAD") -> Path:
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
    with TemporaryDirectory(prefix=".uptimely-", dir=output.parent) as temporary:
        staging = Path(temporary) / "examples"
        staging.mkdir()
        with TemporaryFile() as downloaded:
            with urlopen(url, timeout=30) as response:
                shutil.copyfileobj(response, downloaded)
            downloaded.seek(0)
            with ZipFile(downloaded) as archive:
                _extract_examples(archive, staging)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"Destination already exists: {output}")
        staging.rename(output)
    return output


def main() -> None:
    """Run the Uptimely command-line interface."""
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples = commands.add_parser("examples", help="Manage example projects")
    actions = examples.add_subparsers(dest="action", required=True)
    download = actions.add_parser("download", help="Download examples from public GitHub")
    download.add_argument(
        "--output",
        type=Path,
        default=Path("examples"),
        help="Destination directory (default: examples)",
    )
    download.add_argument(
        "--ref",
        default="HEAD",
        help="Branch, tag, or commit (default: the repository's default branch)",
    )
    args = parser.parse_args()
    try:
        destination = download_examples(args.output, args.ref)
    except (
        OSError,
        URLError,
        HTTPException,
        BadZipFile,
        ValueError,
        PackageNotFoundError,
    ) as error:
        parser.exit(1, f"uptimely: error: {error}\n")
    print(f"Downloaded examples to {destination}")


if __name__ == "__main__":
    main()
