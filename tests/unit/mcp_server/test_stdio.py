"""Verify documented MCP launch paths with real subprocess connections."""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest
from support import examples as example_support

pytest.importorskip("fastmcp", reason="fastmcp extra is not installed")

import fastmcp  # noqa: E402
from fastmcp.client import transports  # noqa: E402

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]


@pytest.mark.anyio
@pytest.mark.parametrize("launcher", ["module", "console", "vscode"])
async def test_documented_stdio_launchers_build_and_execute(
    tmp_path: pathlib.Path,
    example_project_factory: example_support.ProjectFactory,
    launcher: str,
) -> None:
    """Build a copied project and verify discovery and data access over stdio."""
    root = example_project_factory(
        tmp_path / "workspace with spaces" / "examples" / "pump_analytics"
    )
    shutil.copyfile(REPOSITORY_ROOT / "examples" / "__init__.py", root.parent / "__init__.py")
    config_path = root / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["params"] = {
        name: str(REPOSITORY_ROOT / value) for name, value in config["params"].items()
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    executable = pathlib.Path(sys.executable).with_name("uptimely")
    built = subprocess.run(
        [str(executable), "build", str(root)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr

    if launcher == "vscode":
        poetry = shutil.which("poetry")
        if poetry is None:
            pytest.skip("Poetry is not installed")
        workspace = json.loads((REPOSITORY_ROOT / ".vscode" / "mcp.json").read_text())
        server = workspace["servers"]["uptimely"]
        transport = transports.StdioTransport(
            command=poetry,
            args=[*server["args"][:2], "--project-root", str(root)],
            cwd=str(REPOSITORY_ROOT),
        )
    elif launcher == "console":
        transport = transports.StdioTransport(
            command=str(pathlib.Path(sys.executable).with_name("uptimely-mcp")),
            args=["--project-root", str(root)],
            cwd=str(tmp_path),
        )
    else:
        transport = transports.StdioTransport(
            command=sys.executable,
            args=["-m", "uptimely.mcp.server", "--project-root", str(root)],
            cwd=str(tmp_path),
        )

    async with fastmcp.Client(transport, timeout=60) as client:
        tools = {tool.name for tool in await client.list_tools()}
        assert {"describe_spec", "execute_operator", "read_last_run_logs"} <= tools
        described = await client.call_tool("describe_spec")
        assert json.loads(described.content[0].text)["features"] > 0
        executed = await client.call_tool(
            "execute_operator",
            {
                "profile_id": "pump_telemetry",
                "operator_id": "pressure_flow_efficiency",
                "max_rows": 1,
            },
        )
        payload = json.loads(executed.content[0].text)
        assert payload["status"] == "ok", payload
        assert payload["datasets"][0]["row_count"] == 1
        assert "pressure_flow_efficiency" in payload["datasets"][0]["rows"][0]
