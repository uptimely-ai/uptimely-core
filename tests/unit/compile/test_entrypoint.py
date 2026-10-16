import io
import json
import math
import pathlib
import types
from urllib import error, request

import pytest

from uptimely import analytics, compiler, engine, storage
from uptimely import entrypoint as shared_entrypoint
from uptimely.analytics.python import bind, dataset, dimension, feature, mapping, ref
from uptimely.explorer import analytics_render

ANALYTICS_PATH = (
    pathlib.Path(__file__).parents[3]
    / "examples"
    / "pump_analytics"
    / "_generated"
    / "analytics"
    / "analytics.json"
)


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        compiler.Compiler(ANALYTICS_PATH, features="health_signal_normalized")


@pytest.mark.parametrize(
    ("category", "function_id"),
    [("vectorize", "pressure_flow_efficiency"), ("collapse", "maximum")],
)
def test_compiler_rejects_missing_function_entrypoints(category: str, function_id: str) -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    analytics_definition.functions[function_id].entrypoint = ""

    with pytest.raises(ValueError, match=f"Missing entrypoint for function: {function_id}"):
        compiler.Compiler(analytics_definition).compile()


def test_compiler_reports_unreadable_function_signatures() -> None:
    analytics_definition = analytics.load_analytics(ANALYTICS_PATH)
    analytics_definition.functions["pressure_flow_efficiency"].entrypoint = "invalid-entrypoint"

    with pytest.raises(ValueError, match="Could not read signature.*Invalid entrypoint"):
        compiler.Compiler(analytics_definition).compile()


@pytest.mark.parametrize(
    ("entrypoint", "error"),
    [
        ("invalid-entrypoint", ValueError),
        ("uptimely.compiler.plan.models:not_a_function", AttributeError),
    ],
)
def test_load_callable_rejects_invalid_entrypoints(
    entrypoint: str,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        shared_entrypoint.load_callable(entrypoint)


def test_load_callable_accepts_a_function_reference_entrypoint() -> None:
    reference = ref.function(math.ceil)

    assert shared_entrypoint.load_callable(reference.entrypoint)(1.2) == 2


@pytest.mark.parametrize("relative", [False, True, "plain"])
def test_load_callable_accepts_local_file_references(
    tmp_path: pathlib.Path, relative: bool | str
) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("def increment(value: int) -> int:\n    return value + 1\n")
    location = (
        "calculation.py" if relative == "plain" else ("./calculation.py" if relative else str(path))
    )
    reference = ref.function(f"{location}:increment")

    function = shared_entrypoint.load_callable(reference.entrypoint, root=tmp_path)

    assert function(2) == 3
    assert shared_entrypoint.load_callable(reference.entrypoint, root=tmp_path) is function
    assert shared_entrypoint.read_signature(reference.entrypoint, root=tmp_path).returns == "int"


@pytest.mark.parametrize(
    "location",
    [
        "http://example.org/calculation.py",
        "ftp://example.org/calculation.py",
        "git+https://example.org/team/repository.git",
        "git@example.org:team/repository.git",
    ],
)
def test_unsupported_remote_schemes_are_not_loaded(location: str) -> None:
    reference = ref.function(f"{location}:calculate")

    with pytest.raises(ValueError, match="Unsupported function reference scheme"):
        shared_entrypoint.load_callable(reference.entrypoint)


def test_local_file_import_failures_are_not_cached(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("raise RuntimeError('module failed')\n")
    reference = ref.function(f"{path}:calculate")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="module failed"):
            shared_entrypoint.load_callable(reference.entrypoint)


def test_load_callable_rejects_noncallable_attributes() -> None:
    with pytest.raises(TypeError, match="is not callable"):
        shared_entrypoint.load_callable("math:pi")


class _Response(io.BytesIO):
    def __init__(self, source: bytes, url: str) -> None:
        super().__init__(source)
        self.url = url

    def geturl(self) -> str:
        return self.url


@pytest.mark.parametrize("scheme", ["local", "https", "s3"])
def test_source_locations_compile_and_execute(
    scheme: str, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    location = f"{scheme}://test-bucket/{tmp_path.name}/calculation.py"
    path = tmp_path / "calculation.py"
    source = b"""from __future__ import annotations
import polars as pl

def read_values() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "value": [10, 20]})

def calculate(dataset: pl.DataFrame, output: str) -> pl.DataFrame:
    return dataset.with_columns((pl.col("value") + 1).alias(output))
"""
    if scheme == "local":
        path.write_bytes(source)
        location = str(path)
    downloads: list[str] = []
    responses: list[io.BytesIO] = []

    def urlopen(url: str, *, timeout: int) -> _Response:
        assert timeout == shared_entrypoint.REMOTE_READ_TIMEOUT
        downloads.append(url)
        response = _Response(source, url)
        responses.append(response)
        return response

    class Client:
        def get_object(self, *, Bucket: str, Key: str) -> dict[str, io.BytesIO]:
            downloads.append(f"s3://{Bucket}/{Key}")
            response = io.BytesIO(source)
            responses.append(response)
            return {"Body": response}

    def client(service: str) -> Client:
        assert service == "s3"
        return Client()

    monkeypatch.setattr(request, "urlopen", urlopen)
    monkeypatch.setattr(storage, "boto3", types.SimpleNamespace(client=client))
    analytics_definition = analytics.from_python(
        dimensions=[dimension.Dimension(id="id", type="integer")],
        datasets=[
            dataset.Dataset(
                id="observations",
                mappings=[
                    mapping.Mapping(
                        bind=bind.bind(ref.function(f"{location}:read_values", operation="read")),
                        outputs=[
                            feature.Feature(id="id", type="integer"),
                            feature.Feature(id="value", type="integer"),
                        ],
                    ),
                    mapping.Mapping(
                        bind=bind.bind(
                            ref.function(f"{location}:calculate", operation="vectorize"),
                            dataset=ref.current_dataset().dataframe,
                            output="result",
                        ),
                        inputs=[ref.feature("value")],
                        outputs=[feature.Feature(id="result", type="integer")],
                    ),
                ],
            )
        ],
    )

    compiled = compiler.Compiler(analytics_definition).compile()
    result = engine.Engine(compiled).execute()

    assert not result.failures
    assert result.datasets["entity", "observations"].sort("id")["result"].to_list() == [11, 21]
    expected_downloads = [] if scheme == "local" else [location]
    assert downloads == expected_downloads
    if scheme == "https":
        assert all(response.closed for response in responses)
    assert shared_entrypoint.read_signature(f"{location}:calculate").args == {
        "dataset": "DataFrame",
        "output": "str",
    }
    reference_data = analytics_render.create_json(analytics_definition, tmp_path / "docs.json")
    configuration = json.loads(reference_data.read_text(encoding="utf-8"))["configuration"]
    expected_file = path.as_uri() if scheme == "local" else location
    assert configuration["functions"]["calculate"]["entrypoint_file"] == expected_file
    assert downloads == expected_downloads


def test_https_loading_propagates_download_errors_and_can_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    location = f"https://example.org/{tmp_path.name}/calculation.py"

    def failure(url: str, *, timeout: int) -> _Response:
        raise error.HTTPError(url, 403, "Forbidden", None, None)

    monkeypatch.setattr(request, "urlopen", failure)
    for _ in range(2):
        with pytest.raises(error.HTTPError, match="403"):
            shared_entrypoint.load_callable(f"{location}:calculate")

    def success(url: str, *, timeout: int) -> _Response:
        return _Response(b"def calculate():\n    return 42\n", url)

    monkeypatch.setattr(request, "urlopen", success)
    assert shared_entrypoint.load_callable(f"{location}:calculate")() == 42


def test_s3_loading_reports_missing_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(storage, "boto3", None)
    with pytest.raises(ModuleNotFoundError, match=r"uptimely-core\[s3\]"):
        shared_entrypoint.load_callable(f"s3://bucket/{tmp_path.name}/module.py:calculate")


def test_remote_source_execution_failures_are_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def failure(url: str, *, timeout: int) -> _Response:
        return _Response(b"raise RuntimeError('module failed')\n", url)

    monkeypatch.setattr(request, "urlopen", failure)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="module failed"):
            shared_entrypoint.load_callable(
                f"https://example.org/{tmp_path.name}/module.py:calculate"
            )


@pytest.mark.parametrize("location", ["https://example.org", "s3://bucket/"])
def test_remote_locations_must_identify_source_files(location: str) -> None:
    with pytest.raises(ValueError, match="must point to a source file"):
        shared_entrypoint.load_callable(f"{location}:calculate")


def test_https_loading_rejects_redirects_to_other_schemes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def redirect(url: str, *, timeout: int) -> _Response:
        return _Response(b"raise AssertionError('must not run')", "http://example.org/module.py")

    monkeypatch.setattr(request, "urlopen", redirect)
    with pytest.raises(ValueError, match="must not redirect"):
        shared_entrypoint.load_callable(f"https://example.org/{tmp_path.name}/module.py:calculate")
