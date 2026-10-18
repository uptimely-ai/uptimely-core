"""Read local files and S3 objects through a shared storage interface."""

import pathlib

try:
    import boto3
    from botocore import exceptions
except ModuleNotFoundError as error:
    if error.name not in {"boto3", "botocore"}:
        raise
    boto3 = None
    exceptions = None


class Storage:
    """Read spec files from local disk or S3 depending on the path scheme."""

    S3_PREFIX = "s3://"

    @classmethod
    def read(cls, path: str | pathlib.Path) -> str:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return cls._read_s3(path_str)
        return pathlib.Path(path_str).read_text(encoding="utf-8")

    @classmethod
    def is_dir(cls, path: str | pathlib.Path) -> bool:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return path_str.endswith("/")
        return pathlib.Path(path_str).is_dir()

    @classmethod
    def exists(cls, path: str | pathlib.Path) -> bool:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return cls._exists_s3(path_str)
        return pathlib.Path(path_str).exists()

    @classmethod
    def join(cls, base: str | pathlib.Path, *parts: str) -> str:
        """Join a relative path onto a base, preserving the s3:// scheme if present."""
        base_str = str(base)
        if base_str.startswith(cls.S3_PREFIX):
            segments = [base_str.rstrip("/")] + [part.strip("/") for part in parts]
            return "/".join(segments)
        return str(pathlib.Path(base_str, *parts))

    @classmethod
    def parent(cls, path: str | pathlib.Path) -> str:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return path_str.rsplit("/", 1)[0] + "/"
        return str(pathlib.Path(path_str).parent)

    @classmethod
    def _read_s3(cls, uri: str) -> str:
        """Read an S3 object, requiring the optional S3 dependencies."""
        if boto3 is None:
            raise ModuleNotFoundError("S3 storage requires 'uptimely-core[s3]'")

        bucket, _, key = uri[len(cls.S3_PREFIX) :].partition("/")
        client = boto3.client("s3")
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    @classmethod
    def _exists_s3(cls, uri: str) -> bool:
        """Check an S3 object, requiring the optional S3 dependencies."""
        if boto3 is None or exceptions is None:
            raise ModuleNotFoundError("S3 storage requires 'uptimely-core[s3]'")

        bucket, _, key = uri[len(cls.S3_PREFIX) :].partition("/")
        client = boto3.client("s3")
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except exceptions.ClientError as error:
            # 404/NoSuchKey mean "missing"; 403 and others must not masquerade as missing.
            if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise


__all__ = ["Storage"]
