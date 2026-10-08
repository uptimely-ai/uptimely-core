import sys
import types
from pathlib import Path

import pytest

from uptimely.spec.storage import Storage


def test_storage_reads_and_inspects_local_paths(tmp_path: Path) -> None:
    file_path = tmp_path / "spec.json"
    file_path.write_text('{"version": "0.1.0"}', encoding="utf-8")

    assert Storage.read(file_path) == '{"version": "0.1.0"}'
    assert Storage.exists(file_path)
    assert Storage.is_dir(tmp_path)
    assert Storage.join(tmp_path, "nested", "spec.json") == str(tmp_path / "nested" / "spec.json")
    assert Storage.parent(file_path) == str(tmp_path)


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
    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = ClientError
    botocore.exceptions = exceptions
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exceptions)

    assert Storage.read("s3://bucket/spec.json") == '{"version": "0.1.0"}'
    assert Storage.exists("s3://bucket/spec.json")
    client.exists = False
    assert not Storage.exists("s3://bucket/missing.json")
    assert Storage.is_dir("s3://bucket/prefix/")
    assert (
        Storage.join("s3://bucket/prefix/", "nested", "spec.json")
        == "s3://bucket/prefix/nested/spec.json"
    )
    assert Storage.parent("s3://bucket/prefix/spec.json") == "s3://bucket/prefix/"
    assert client.requests == [
        ("get", "bucket", "spec.json"),
        ("head", "bucket", "spec.json"),
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
    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = ClientError
    botocore.exceptions = exceptions
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exceptions)

    with pytest.raises(ClientError):
        Storage.exists("s3://bucket/spec.json")
