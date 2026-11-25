"""Tests for the packaged Explorer frontend and snapshot API."""

import asyncio
import datetime
import io
import json
import logging
import pathlib
import urllib.parse
import zipfile

import polars as pl
import pytest
from starlette.types import ASGIApp, Message, Scope

from uptimely import application, engine, spec
from uptimely import plan as execution_plan
from uptimely.cli import explorer
from uptimely.explorer import server as explorer_server
from uptimely.run import store as run_store
from uptimely.test import models as test_models
from uptimely.test import store as test_store


def _snapshot(name: str = "Example project") -> dict[str, object]:
    return {
        "format_version": 5,
        "project": {"name": name, "spec_version": 3},
        "build": {
            "built_at": "2026-11-25T06:00:00+00:00",
            "build_version": 6,
            "uptimely_version": "test",
            "features": None,
            "spec_source": None,
            "code_language": None,
        },
        "scope": {"label": "all features", "features": None, "is_scoped": False},
        "catalogs": {
            "configuration": {},
            "summary": {},
            "feature_dependencies": [],
            "function_groups": {},
        },
        "graphs": {
            "feature_lineage": {"nodes": [], "links": []},
            "feature_style": {},
            "invocation_lineage": {"nodes": [], "links": []},
            "invocation_style": {},
        },
        "plan": {"stage_count": 0, "invocation_count": 0},
        "stages": [],
        "animation": {"stages": []},
    }


def _get(app: ASGIApp, path: str) -> tuple[int, bytes, dict[str, str]]:
    async def request() -> tuple[int, bytes, dict[str, str]]:
        messages: list[Message] = []
        request_sent = False

        async def receive() -> Message:
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            messages.append(message)

        url = urllib.parse.urlsplit(path)
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode(),
            "query_string": url.query.encode(),
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8001),
        }
        await app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        status = start["status"]
        headers = {key.decode().lower(): value.decode() for key, value in start.get("headers", [])}
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return status, body, headers

    return asyncio.run(request())


def _saved_run(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> engine.Engine:
    source = tmp_path / "spec.json"
    spec.write_document(spec.Spec(), source)
    bundle = application.build(tmp_path, json_spec=source)
    runtime = engine.Engine(bundle, engine.EngineConfig())

    def execute(**kwargs: object) -> engine.ExecutionResult:
        logging.getLogger("uptimely.engine").warning("saved message")
        return engine.ExecutionResult(
            datasets={"sample": pl.DataFrame({"value": [1, 2, 3]})},
            calculated_outputs={},
            invocation_statuses={},
            durations={},
            failures={},
            plan_version=execution_plan.PLAN_VERSION,
        )

    monkeypatch.setattr(runtime, "_execute", execute)
    runtime.run(preview_rows=2)
    return runtime


@pytest.mark.parametrize("path", ["/", "/css/spec.css", "/js/catalogs/catalog_renderer.js"])
def test_frontend_assets_require_cache_revalidation(tmp_path: pathlib.Path, path: str) -> None:
    app = explorer_server.create_app(tmp_path)
    status, body, headers = _get(app, path)
    assert status == 200
    assert body
    assert headers["cache-control"] == "no-cache"
    assert "etag" in headers


def test_run_api_reads_fresh_metadata_previews_and_logs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = explorer_server.create_app(tmp_path)
    assert _get(app, "/api/run")[0] == 404
    runtime = _saved_run(tmp_path, monkeypatch)

    status, body, headers = _get(app, "/api/run")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    manifest = json.loads(body)
    run_id = manifest["run_id"]
    assert manifest["status"] == "succeeded"
    assert "format_version" not in manifest

    status, body, headers = _get(app, f"/api/run/preview/sample?run_id={run_id}")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert json.loads(body)["rows"] == [[1], [2]]
    status, body, _ = _get(app, f"/api/run/logs?run_id={run_id}&offset=0&limit=1")
    assert status == 200
    assert json.loads(body)[0]["message"] == "saved message"
    assert _get(app, "/api/run/preview/missing")[0] == 404
    for query in ("offset=-1", "limit=0", "limit=1001", "limit=invalid"):
        assert _get(app, f"/api/run/logs?{query}")[0] == 422

    runtime.run()
    assert json.loads(_get(app, "/api/run")[1])["run_id"] != run_id
    assert _get(app, f"/api/run/preview/sample?run_id={run_id}")[0] == 409
    assert _get(app, f"/api/run/logs?run_id={run_id}")[0] == 409


@pytest.mark.parametrize("old_version", [1, 2, 3])
def test_test_api_reads_latest_valid_report_without_caching(
    tmp_path: pathlib.Path, old_version: int
) -> None:
    app = explorer_server.create_app(tmp_path)
    assert _get(app, "/api/test")[0] == 404
    report = test_models.TestReport(
        started_at=datetime.datetime(2026, 11, 24, tzinfo=datetime.UTC),
        finished_at=datetime.datetime(2026, 11, 24, 0, 1, tzinfo=datetime.UTC),
        status="failed",
        cases=[
            test_models.CaseResult(
                profile="pump",
                operator="calculate",
                case="basic",
                status="failed",
                data=test_models.Case.model_validate(
                    {"inputs": {"dataset": [{"x": 1}]}, "expected": {"return": [{"x": 2}]}}
                ),
                actual=[{"x": 3}],
                call=test_models.ResolvedCall(
                    function="example:calculate",
                    arguments={"dataset": "$dataset", "limit": 7},
                    dataframe_inputs={"/dataset": "dataset"},
                ),
            )
        ],
    )
    report_path = tmp_path / "artifacts" / "test" / "test.json"
    tests = test_store.TestStore(tmp_path)
    tests.save_cases(report)
    tests.save_report(report)

    status, body, headers = _get(app, "/api/test")

    assert status == 200
    assert headers["cache-control"] == "no-store"
    case = json.loads(body)["cases"][0]
    assert "data" not in case
    status, body, _ = _get(app, "/api/test/cases/pump?started_at=2026-11-24T00%3A00%3A00Z")
    assert status == 200
    details = json.loads(body)["calculate"]["cases"]["basic"]
    assert details["expected"]["return"] == [{"x": 2}]
    assert details["actual"] == [{"x": 3}]
    assert details["call"] == {
        "function": "example:calculate",
        "arguments": {"dataset": "$dataset", "limit": 7},
        "dataframe_inputs": {"/dataset": "dataset"},
    }
    assert _get(app, "/api/test/cases/pump?started_at=2026-11-23T00%3A00%3A00Z")[0] == 409
    assert _get(app, "/api/test/cases/other?started_at=2026-11-24T00%3A00%3A00Z")[0] == 404
    (tmp_path / "artifacts" / "test" / "cases" / "pump.json").unlink()
    assert _get(app, "/api/test/cases/pump?started_at=2026-11-24T00%3A00%3A00Z")[0] == 503

    report_path.write_text(
        json.dumps(
            {
                "version": old_version,
                "started_at": "2026-11-24T00:00:00Z",
                "status": "passed",
                "cases": [
                    {
                        "profile": "pump",
                        "operator": "calculate",
                        "case": "basic",
                        "status": "passed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    status, body, _ = _get(app, "/api/test")
    assert status == 200
    assert json.loads(body)["cases"][0]["data"] is None
    assert json.loads(body)["cases"][0]["call"] is None


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_test_api_reports_incomplete_reports(tmp_path: pathlib.Path, damage: str) -> None:
    report_path = tmp_path / "artifacts" / "test" / "test.json"
    report_path.parent.mkdir(parents=True)
    if damage == "corrupt":
        report_path.write_text("{", encoding="utf-8")

    status, body, _ = _get(explorer_server.create_app(tmp_path), "/api/test")

    assert status == (404 if damage == "missing" else 503)
    assert json.loads(body)["detail"]


@pytest.mark.parametrize("artifact", ["run.json", "preview/sample.json", "log.jsonl"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_run_api_reports_invalid_or_missing_artifacts(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, artifact: str, damage: str
) -> None:
    _saved_run(tmp_path, monkeypatch)
    saved = run_store.RunStore(tmp_path)
    path = saved.root / artifact
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("{", encoding="utf-8")
    endpoint = {
        "run.json": "/api/run",
        "preview/sample.json": "/api/run/preview/sample",
        "log.jsonl": "/api/run/logs",
    }[artifact]

    status, body, _ = _get(explorer_server.create_app(tmp_path), endpoint)

    assert status == (404 if artifact == "run.json" and damage == "missing" else 503)
    assert json.loads(body)["detail"]


def test_app_serves_packaged_frontend_and_reads_fresh_snapshot(tmp_path: pathlib.Path) -> None:
    snapshot_path = tmp_path / application.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    app = explorer_server.create_app(tmp_path)

    status, body, _ = _get(app, "/")
    assert status == 200
    assert b"Analytics Explorer" in body
    assert _get(app, "/css/explorer.css")[0] == 200
    for path in (
        "/js/application/bootstrap.js",
        "/js/application/view_controller.js",
        "/js/catalogs/catalog_renderer.js",
        "/js/lineage/feature_lineage.js",
        "/js/animation/playback_controller.js",
        "/js/rendering/shared_markup.js",
        "/js/navigation/sidebar_controls.js",
        "/js/theme/tailwind_theme.js",
    ):
        assert _get(app, path)[0] == 200

    status, body, headers = _get(app, "/api/explorer")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert json.loads(body)["project"]["name"] == "Example project"

    snapshot_path.write_text(json.dumps(_snapshot("Rebuilt project")), encoding="utf-8")
    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "Rebuilt project"


def test_api_reads_snapshot_after_project_rebuild(tmp_path: pathlib.Path) -> None:
    project_root = tmp_path / "project"
    spec_path = project_root / "spec.json"
    definition = spec.Spec(name="Before rebuild")
    spec.write_document(definition, spec_path)
    application.build(project_root, json_spec=spec_path)
    app = explorer_server.create_app(project_root)

    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "Before rebuild"

    definition.name = "After rebuild"
    spec.write_document(definition, spec_path)
    application.build(project_root, json_spec=spec_path)

    assert json.loads(_get(app, "/api/explorer")[1])["project"]["name"] == "After rebuild"


@pytest.mark.parametrize("kind", ["missing", "corrupt", "unsupported"])
def test_snapshot_api_reports_rebuild_instructions(tmp_path: pathlib.Path, kind: str) -> None:
    snapshot_path = tmp_path / application.EXPLORER_DATA_FILE
    if kind != "missing":
        snapshot_path.parent.mkdir(parents=True)
        content = "not json" if kind == "corrupt" else json.dumps({"format_version": 99})
        snapshot_path.write_text(content, encoding="utf-8")

    status, body, _ = _get(explorer_server.create_app(tmp_path), "/api/explorer")

    assert status == 503
    assert "uptimely build" in json.loads(body)["detail"]


def test_export_route_returns_static_zip_with_relative_data_url(
    tmp_path: pathlib.Path,
) -> None:
    snapshot_path = tmp_path / application.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")

    status, body, headers = _get(explorer_server.create_app(tmp_path), "/api/explorer/export")

    assert status == 200
    assert headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert json.loads(archive.read("data/explorer.json")) == _snapshot()
        assert '"./data/explorer.json"' in archive.read("config.js").decode("utf-8")


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_create_app_rejects_missing_project_root(tmp_path: pathlib.Path, kind: str) -> None:
    project_root = tmp_path / "project"
    if kind == "file":
        project_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        explorer_server.create_app(project_root)


def test_serve_explorer_uses_uvicorn_without_a_build_lock(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    snapshot_path = root / application.EXPLORER_DATA_FILE
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")
    calls: list[tuple[str, int]] = []
    cwd = pathlib.Path.cwd()

    def run(app: ASGIApp, host: str, port: int) -> None:
        calls.append((host, port))
        assert _get(app, "/")[0] == 200
        assert _get(app, "/api/explorer")[0] == 200
        with application.build_lock(root, exclusive=True, wait=False):
            pass
        raise KeyboardInterrupt

    monkeypatch.setattr(explorer_server.uvicorn, "run", run)
    caplog.set_level(logging.INFO, logger="uptimely.explorer.server")

    explorer.serve_explorer(root, port=0, scope="selected features: pressure")

    assert pathlib.Path.cwd() == cwd
    assert calls == [("127.0.0.1", 0)]
    assert "http://127.0.0.1:0/" not in caplog.text
    assert "build scope: selected features: pressure" in caplog.text
    assert "Spec explorer server stopped." in caplog.text


def test_serve_explorer_propagates_server_errors(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.mkdir(exist_ok=True)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(explorer_server.uvicorn, "run", fail)

    with pytest.raises(OSError, match="address already in use"):
        explorer.serve_explorer(tmp_path, port=8001)
