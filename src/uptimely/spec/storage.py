from pathlib import Path


class Storage:
    """Read specification files from local disk or S3 depending on the path scheme."""

    S3_PREFIX = "s3://"

    @classmethod
    def read(cls, path: str | Path) -> str:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return cls._read_s3(path_str)
        return Path(path_str).read_text(encoding="utf-8")

    @classmethod
    def is_dir(cls, path: str | Path) -> bool:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return path_str.endswith("/")
        return Path(path_str).is_dir()

    @classmethod
    def exists(cls, path: str | Path) -> bool:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return cls._exists_s3(path_str)
        return Path(path_str).exists()

    @classmethod
    def join(cls, base: str | Path, *parts: str) -> str:
        """Join a relative path onto a base, preserving the s3:// scheme if present."""
        base_str = str(base)
        if base_str.startswith(cls.S3_PREFIX):
            segments = [base_str.rstrip("/")] + [part.strip("/") for part in parts]
            return "/".join(segments)
        return str(Path(base_str, *parts))

    @classmethod
    def parent(cls, path: str | Path) -> str:
        path_str = str(path)
        if path_str.startswith(cls.S3_PREFIX):
            return path_str.rsplit("/", 1)[0] + "/"
        return str(Path(path_str).parent)

    @classmethod
    def _read_s3(cls, uri: str) -> str:
        import boto3  # imported lazily so boto3 stays an optional dependency

        bucket, _, key = uri[len(cls.S3_PREFIX) :].partition("/")
        client = boto3.client("s3")
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    @classmethod
    def _exists_s3(cls, uri: str) -> bool:
        import boto3
        from botocore.exceptions import ClientError

        bucket, _, key = uri[len(cls.S3_PREFIX) :].partition("/")
        client = boto3.client("s3")
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as error:
            # 404/NoSuchKey mean "missing"; 403 and others must not masquerade as missing.
            if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise
