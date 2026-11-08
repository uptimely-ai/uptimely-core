"""Shared CLI failure-reporting contracts."""

import argparse
import logging

import pytest

from uptimely.cli import common


@pytest.mark.parametrize("level", common.LOG_LEVELS)
def test_exit_with_error_reports_chained_tracebacks_only_at_debug(
    level: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with common.apply_log_level(level):
        try:
            try:
                raise AttributeError("missing python_spec")
            except AttributeError as cause:
                raise ValueError("source loading failed") from cause
        except ValueError as error:
            with pytest.raises(SystemExit) as exit_error:
                common.exit_with_error(argparse.ArgumentParser(), error)

    assert exit_error.value.code == 1
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("uptimely: error: source loading failed\n")
    if level == "debug":
        assert "Traceback (most recent call last):" in output.err
        assert __file__ in output.err
        assert "AttributeError: missing python_spec" in output.err
        assert "direct cause" in output.err
        assert "ValueError: source loading failed" in output.err
    else:
        assert output.err == "uptimely: error: source loading failed\n"


def test_error_reporting_restores_log_level() -> None:
    logger = logging.getLogger("uptimely")
    previous_level = logger.level

    with pytest.raises(SystemExit), common.apply_log_level("debug"):
        common.exit_with_error(argparse.ArgumentParser(), ValueError("failure"))

    assert logger.level == previous_level
