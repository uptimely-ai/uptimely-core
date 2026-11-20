import io
import logging
import pathlib
import re
import sys
import types

import pytest

from uptimely.cli import cli


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    cli.main()


@pytest.mark.parametrize(
    ("level", "color"),
    [
        (logging.DEBUG, "\033[36m"),
        (logging.INFO, "\033[32m"),
        (logging.WARNING, "\033[33m"),
        (logging.ERROR, "\033[31m"),
        (logging.CRITICAL, "\033[1;31m"),
    ],
)
def test_color_formatter_respects_terminal_and_environment(
    monkeypatch: pytest.MonkeyPatch,
    level: int,
    color: str,
) -> None:
    class TerminalOutput(io.StringIO):
        def isatty(self) -> bool:
            return True

    formatter = cli._ColorFormatter("%(message)s")
    record = logging.LogRecord("test", level, __file__, 1, "debug trace\n/path/to/file", (), None)
    message = "debug trace\n/path/to/file"
    plain_level_field = f"{record.levelname:8}"
    colored_level_field = (
        plain_level_field
        if level >= logging.ERROR
        else f"{color}{record.levelname}\033[0m{' ' * (8 - len(record.levelname))}"
    )
    plain_message = f"{plain_level_field} | {message}"
    colored_message = f"{colored_level_field} | {message}"
    colored = colored_message
    if level >= logging.ERROR:
        colored = f"{color}{plain_message}\033[0m"
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys, "stdout", TerminalOutput())

    assert formatter.format(record) == colored
    assert record.getMessage() == message
    assert record.levelname == logging.getLevelName(level)

    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert formatter.format(record) == plain_message

    monkeypatch.setattr(sys, "stdout", TerminalOutput())
    assert formatter.format(record) == colored

    monkeypatch.setenv("NO_COLOR", "1")
    assert formatter.format(record) == plain_message


@pytest.mark.parametrize(
    "module",
    [
        "uptimely.cli",
        "uptimely.spec.validation.rules.profile_identity",
        "uptimely.spec.validation.rules.profile_identity.extra",
        "third_party.uptimely.client",
    ],
)
def test_formatter_omits_source_fields_without_changing_logger_name(
    monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    record = logging.LogRecord(module, logging.DEBUG, __file__, 1, "Message", (), None)

    output = cli._ColorFormatter("%(message)s").format(record)

    assert output == "DEBUG    | Message"
    assert record.name == module


def test_formatter_removes_leading_newlines_but_preserves_message_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    record = logging.LogRecord(
        "uptimely.engine", logging.INFO, __file__, 1, "\n\nSummary\n  table", (), None
    )

    output = cli._ColorFormatter("%(message)s").format(record)

    assert output == "INFO     | Summary\n  table"


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.ERROR, logging.CRITICAL])
@pytest.mark.parametrize("no_color", [False, True])
@pytest.mark.parametrize("columns", [30, 60, 100])
def test_formatter_wraps_terminal_messages_under_message_column(
    monkeypatch: pytest.MonkeyPatch, level: int, no_color: bool, columns: int
) -> None:
    class TerminalOutput(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdout", TerminalOutput())
    monkeypatch.setattr(
        cli.shutil, "get_terminal_size", lambda: types.SimpleNamespace(columns=columns)
    )
    monkeypatch.delenv("NO_COLOR", raising=False)
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    message = "Check required dimension columns for vectorize result " + "x" * 110
    record = logging.LogRecord("uptimely.engine", level, __file__, 1, message, (), None)

    output = cli._ColorFormatter("%(message)s").format(record)
    plain = re.sub(r"\033\[[0-9;]*m", "", output)
    lines = plain.splitlines()

    assert len(lines) > 1
    assert lines[0].startswith(f"{record.levelname:8} | ")
    assert all(line.startswith("         | ") for line in lines[1:])
    assert all(len(line) < columns for line in lines)
    assert "".join(line[11:] for line in lines).replace(" ", "") == message.replace(" ", "")
    assert record.getMessage() == message
    assert ("\033[" in output) is not no_color

    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert cli._ColorFormatter("%(message)s").format(record) == f"{record.levelname:8} | {message}"


def test_formatter_preserves_multiline_terminal_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TerminalOutput(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdout", TerminalOutput())
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(cli.shutil, "get_terminal_size", lambda: types.SimpleNamespace(columns=25))
    message = "Summary\n  | column with intentional spacing and long content |\nTraceback:\n  frame"
    record = logging.LogRecord("uptimely.engine", logging.INFO, __file__, 1, message, (), None)

    assert cli._ColorFormatter("%(message)s").format(record) == f"INFO     | {message}"


@pytest.mark.parametrize("terminal", [False, True])
@pytest.mark.parametrize("no_color", [False, True])
@pytest.mark.parametrize(
    ("arguments", "status"),
    [
        (("--invalid-option",), 2),
        (("run", "--log-level", "INFO"), 2),
        (("build", "--log-level", "INFO"), 2),
        (("run", "--preview", "0"), 2),
        (("run", "--build"), 1),
    ],
)
def test_cli_errors_use_stderr_terminal_colors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    terminal: bool,
    no_color: bool,
    arguments: tuple[str, ...],
    status: int,
) -> None:
    class ErrorOutput(io.StringIO):
        def isatty(self) -> bool:
            return terminal

    output = ErrorOutput()
    monkeypatch.setattr(sys, "stderr", output)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *arguments)

    assert error.value.code == status
    message = output.getvalue()
    assert ": error:" not in message
    assert ("\033[31m" in message) is (terminal and not no_color)
    if terminal and not no_color:
        assert "\033[31mERROR    | " in message
        assert message.count("\033[") == 2
        assert message.endswith("\n\033[0m")
    else:
        assert "ERROR    |" in message
        assert "\033[" not in message
        assert message.endswith("\n")
