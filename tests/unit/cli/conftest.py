"""Isolate CLI logging handlers bound to per-test capture streams."""

import logging
from collections import abc

import pytest

from uptimely.cli import cli


@pytest.fixture(autouse=True)
def cleanup_cli_logging() -> abc.Iterator[None]:
    """Remove CLI-owned handlers before their capture streams expire."""
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler.formatter, cli._ColorFormatter):
            root.removeHandler(handler)
            handler.close()
