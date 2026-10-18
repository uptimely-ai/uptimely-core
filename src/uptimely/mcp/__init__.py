"""MCP server exposing spec introspection and execution as agent tools."""

from .server import create_server, main

__all__ = ["create_server", "main"]
