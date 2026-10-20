import io
import math
import pathlib
import types
from urllib import error, request

import pytest
from conftest import EXAMPLES_ROOT

from uptimely import compiler, engine, spec, storage
from uptimely import entrypoint as shared_entrypoint
from uptimely.explorer import spec_render
from uptimely.spec.python import bind, dataset, dimension, feature, mapping, ref

SPEC_PATH = EXAMPLES_ROOT / "pump_analytics/_generated/build/spec.json"


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        compiler.Compiler(SPEC_PATH, features="health_signal_normalized")


@pytest.mark.parametrize(
    ("category", "function_id"),
    [("vectorize", "pressure_flow_efficiency"), ("collapse", "maximum")],
)
def test_compiler_rejects_missing_function_entrypoints(category: str, function_id: str) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions[function_id].entrypoint = ""

    with pytest.raises(ValueError, match=f"Missing entrypoint for function: {function_id}"):
        compiler.Compiler(spec_definition).compile()


def test_compiler_reports_unreadable_function_signatures() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["pressure_flow_efficiency"].entrypoint = "invalid-entrypoint"

    with pytest.raises(ValueError, match="Could not read signature.*Invalid entrypoint"):
        compiler.Compiler(spec_definition).compile()


@pytest.mark.parametrize(
    ("entrypoint", "error"),
    [
        ("invalid-entrypoint", ValueError),
        ("uptimely.compiler.plan.models:not_a_function", AttributeError),
    ],
)
def test_function_load_rejects_invalid_entrypoints(
    entrypoint: str,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        shared_entrypoint.Entrypoint(entrypoint).function.load()


def test_function_load_accepts_a_function_reference_entrypoint() -> None:
    reference = ref.function(math.ceil)

    assert shared_entrypoint.Entrypoint(reference.entrypoint).function.load()(1.2) == 2


@pytest.mark.parametrize("relative", [False, True, "plain"])
def test_function_load_accepts_local_file_references(
    tmp_path: pathlib.Path, relative: bool | str
) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("def increment(value: int) -> int:\n    return value + 1\n")
    location = (
        "calculation.py" if relative == "plain" else ("./calculation.py" if relative else str(path))
    )
    reference = ref.function(f"{location}:increment")

    entrypoint = shared_entrypoint.Entrypoint(reference.entrypoint, root=tmp_path)
    function = entrypoint.function.load()

    assert function(2) == 3
    assert entrypoint.function.load() is function
    assert entrypoint.function.signature.returns == "int"
    assert shared_entrypoint.Signature.read(entrypoint.function).returns == "int"
    assert shared_entrypoint.TypeAnnotation.name(int | None) == "int | None"
    assert entrypoint.module.load() is entrypoint.function.module.load()


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
        shared_entrypoint.Entrypoint(reference.entrypoint).function.load()


def test_local_file_import_failures_are_not_cached(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "calculation.py"
    path.write_text("raise RuntimeError('module failed')\n")
    reference = ref.function(f"{path}:calculate")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="module failed"):
            shared_entrypoint.Entrypoint(reference.entrypoint).function.load()


def test_function_load_rejects_noncallable_attributes() -> None:
    with pytest.raises(TypeError, match="is not callable"):
        shared_entrypoint.Entrypoint("math:pi").function.load()


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
    spec_definition = spec.from_python(
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

    compiled = compiler.Compiler(spec_definition).compile()
    result = engine.Engine(compiled).execute()

    assert not result.failures
    assert result.datasets["entity", "observations"].sort("id")["result"].to_list() == [11, 21]
    expected_downloads = [] if scheme == "local" else [location]
    assert downloads == expected_downloads
    if scheme == "https":
        assert all(response.closed for response in responses)
    entrypoint = shared_entrypoint.Entrypoint(f"{location}:calculate")
    assert entrypoint.function.signature.args == {
        "dataset": "DataFrame",
        "output": "str",
    }
    if scheme != "local":
        assert entrypoint.module.load_external() is entrypoint.module.load()
    configuration = spec_render._build_context(spec_definition, False).configuration
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
            shared_entrypoint.Entrypoint(f"{location}:calculate").function.load()

    def success(url: str, *, timeout: int) -> _Response:
        return _Response(b"def calculate():\n    return 42\n", url)

    monkeypatch.setattr(request, "urlopen", success)
    assert shared_entrypoint.Entrypoint(f"{location}:calculate").function.load()() == 42


def test_s3_loading_reports_missing_optional_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(storage, "boto3", None)
    with pytest.raises(ModuleNotFoundError, match=r"uptimely-core\[s3\]"):
        shared_entrypoint.Entrypoint(
            f"s3://bucket/{tmp_path.name}/module.py:calculate"
        ).function.load()


def test_remote_source_execution_failures_are_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def failure(url: str, *, timeout: int) -> _Response:
        return _Response(b"raise RuntimeError('module failed')\n", url)

    monkeypatch.setattr(request, "urlopen", failure)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="module failed"):
            shared_entrypoint.Entrypoint(
                f"https://example.org/{tmp_path.name}/module.py:calculate"
            ).function.load()


@pytest.mark.parametrize("location", ["https://example.org", "s3://bucket/"])
def test_remote_locations_must_identify_source_files(location: str) -> None:
    with pytest.raises(ValueError, match="must point to a source file"):
        shared_entrypoint.Entrypoint(f"{location}:calculate").function.load()


def test_https_loading_rejects_redirects_to_other_schemes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def redirect(url: str, *, timeout: int) -> _Response:
        return _Response(b"raise AssertionError('must not run')", "http://example.org/module.py")

    monkeypatch.setattr(request, "urlopen", redirect)
    with pytest.raises(ValueError, match="must not redirect"):
        shared_entrypoint.Entrypoint(
            f"https://example.org/{tmp_path.name}/module.py:calculate"
        ).function.load()
