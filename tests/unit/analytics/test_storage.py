import pathlib
import subprocess
import sys
import types

import pytest

from uptimely import storage


def test_storage_reads_and_inspects_local_paths(tmp_path: pathlib.Path) -> None:
    file_path = tmp_path / "analytics.json"
    file_path.write_text('{"version": "0.1.0"}', encoding="utf-8")

    assert storage.Storage.read(file_path) == '{"version": "0.1.0"}'
    assert storage.Storage.exists(file_path)
    assert storage.Storage.is_dir(tmp_path)
    assert storage.Storage.join(tmp_path, "nested", "analytics.json") == str(
        tmp_path / "nested" / "analytics.json"
    )
    assert storage.Storage.parent(file_path) == str(tmp_path)


def test_storage_reads_and_checks_s3_paths_with_mocked_client(monkeypatch) -> None:
    class ClientError(Exception):
        def __init__(self, code: str = "404") -> None:
            super().__init__(code)
            self.response = {"Error": {"Code": code}}

    class Body:
        def read(self) -> bytes:
            return b'{"version": "0.1.0"}'

    class Client:
        def __init__(self) -> None:
            self.requests: list[tuple[str, str, str]] = []
            self.exists = True

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Body]:
            self.requests.append(("get", Bucket, Key))
            return {"Body": Body()}

        def head_object(self, *, Bucket: str, Key: str) -> None:
            self.requests.append(("head", Bucket, Key))
            if not self.exists:
                raise ClientError()

    client = Client()
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda service: client
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = ClientError
    monkeypatch.setattr(storage, "boto3", boto3)
    monkeypatch.setattr(storage, "exceptions", exceptions)

    assert storage.Storage.read("s3://bucket/analytics.json") == '{"version": "0.1.0"}'
    assert storage.Storage.exists("s3://bucket/analytics.json")
    client.exists = False
    assert not storage.Storage.exists("s3://bucket/missing.json")
    assert storage.Storage.is_dir("s3://bucket/prefix/")
    assert (
        storage.Storage.join("s3://bucket/prefix/", "nested", "analytics.json")
        == "s3://bucket/prefix/nested/analytics.json"
    )
    assert storage.Storage.parent("s3://bucket/prefix/analytics.json") == "s3://bucket/prefix/"
    assert client.requests == [
        ("get", "bucket", "analytics.json"),
        ("head", "bucket", "analytics.json"),
        ("head", "bucket", "missing.json"),
    ]


def test_storage_s3_exists_propagates_non_404_errors(monkeypatch) -> None:
    """Access-denied and other errors must not masquerade as a missing object."""

    class ClientError(Exception):
        def __init__(self, code: str = "403") -> None:
            super().__init__(code)
            self.response = {"Error": {"Code": code}}

    class Client:
        def head_object(self, *, Bucket: str, Key: str) -> None:
            raise ClientError()

    client = Client()
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda service: client
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = ClientError
    monkeypatch.setattr(storage, "boto3", boto3)
    monkeypatch.setattr(storage, "exceptions", exceptions)

    with pytest.raises(ClientError):
        storage.Storage.exists("s3://bucket/analytics.json")


@pytest.mark.parametrize("method", ["read", "exists"])
def test_storage_s3_reports_missing_optional_dependencies(monkeypatch, method: str) -> None:
    monkeypatch.setattr(storage, "boto3", None)
    monkeypatch.setattr(storage, "exceptions", None)

    with pytest.raises(ModuleNotFoundError, match=r"uptimely-core\[s3\]"):
        getattr(storage.Storage, method)("s3://bucket/analytics.json")


def test_core_imports_without_s3_dependencies() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import sys

class BlockS3:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"boto3", "botocore"}:
            raise ModuleNotFoundError(name=fullname)
sys.meta_path.insert(0, BlockS3())
from uptimely import storage
assert storage.boto3 is None
assert storage.exceptions is None
assert storage.Storage.exists("pyproject.toml")
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
