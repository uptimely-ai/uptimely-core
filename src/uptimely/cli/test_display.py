"""Terminal display for operator test cases."""

import datetime
import json
import shutil
import textwrap

import polars as pl
import pydantic

from uptimely.test import models, runner

type Rows = list[dict[str, pydantic.JsonValue]]
type Marks = set[tuple[int, str]]


def show_case(result: models.CaseResult, case: models.Case, actual: pl.DataFrame | None) -> None:
    """Display input, expected output, and a comparison for mismatches."""
    width = max(1, shutil.get_terminal_size(fallback=(80, 24)).columns)
    print()
    identity = _escape(f"{result.profile}/{result.operator}/{result.case}")
    _print_wrapped(f"Case: {identity} ({result.status})", width)

    inputs = list(case.inputs.items())
    if len(inputs) == 1:
        name, rows = inputs[0]
        _print_wrapped("Input and expected output (independent row sets):", width)
        _show_pair(f"Input: {name}", rows, "Expected output", case.expected.return_, width)
    else:
        for name, rows in inputs:
            _show_single(f"Input: {name}", rows, width)
        _show_single("Expected output", case.expected.return_, width)

    if actual is not None:
        expected_marks, actual_marks = _differences(actual, case.expected.return_)
        _print_wrapped("Comparison (! marks differing or missing values):", width)
        _show_pair(
            "Expected output",
            case.expected.return_,
            "Actual output",
            actual.to_dicts(),
            width,
            expected_marks,
            actual_marks,
        )


def _differences(actual: pl.DataFrame, expected: Rows) -> tuple[Marks, Marks]:
    expected_marks: Marks = set()
    actual_marks: Marks = set()
    actual_columns = set(actual.columns)
    for index in range(max(actual.height, len(expected))):
        expected_row = expected[index] if index < len(expected) else {}
        actual_present = index < actual.height
        for column in set(expected_row) | (actual_columns if actual_present else set()):
            expected_present = column in expected_row
            actual_has_value = actual_present and column in actual_columns
            different = not expected_present or not actual_has_value
            if not different:
                try:
                    runner.TestRunner._compare(
                        actual.slice(index, 1).select(column), [{column: expected_row[column]}]
                    )
                except AssertionError:
                    different = True
            if different:
                if expected_present:
                    expected_marks.add((index, column))
                if actual_has_value:
                    actual_marks.add((index, column))
    return expected_marks, actual_marks


def _show_pair(
    left_title: str,
    left: Rows,
    right_title: str,
    right: Rows,
    width: int,
    left_marks: Marks | None = None,
    right_marks: Marks | None = None,
) -> None:
    left_marks = left_marks or set()
    right_marks = right_marks or set()
    left_lines = _table(left, left_marks)
    right_lines = _table(right, right_marks)
    left_heading = _escape(left_title) + ":"
    right_heading = _escape(right_title) + ":"
    left_width = max(map(len, [left_heading, *left_lines]))
    right_width = max(map(len, [right_heading, *right_lines]))
    if left_width + right_width + 3 <= width:
        left_lines = [left_heading, *left_lines]
        right_lines = [right_heading, *right_lines]
        for index in range(max(len(left_lines), len(right_lines))):
            left_line = left_lines[index] if index < len(left_lines) else ""
            right_line = right_lines[index] if index < len(right_lines) else ""
            print(f"{left_line:<{left_width}}   {right_line}".rstrip())
    else:
        _show_single(left_title, left, width, left_marks, left_lines)
        _show_single(right_title, right, width, right_marks, right_lines)


def _show_single(
    title: str,
    rows: Rows,
    width: int,
    marks: Marks | None = None,
    table: list[str] | None = None,
) -> None:
    marks = marks or set()
    lines = table if table is not None else _table(rows, marks)
    _print_wrapped(_escape(title) + ":", width)
    if all(len(line) <= width for line in lines):
        for line in lines:
            print(line)
    elif lines and lines[0].startswith("Cannot display dataframe:"):
        for line in lines:
            _print_wrapped(line, width)
    else:
        for line in _panels(rows, marks, width):
            print(line)


def _table(rows: Rows, marks: Marks) -> list[str]:
    try:
        pl.DataFrame(rows)
    except (pl.exceptions.PolarsError, TypeError, ValueError, OverflowError) as error:
        return [f"Cannot display dataframe: {_escape(f'{type(error).__name__}: {error}')}"]
    if not rows:
        return ["(no rows)"]
    headers, values = _cells(rows, marks)
    widths = [max(len(row[i]) for row in [headers, *values]) for i in range(len(headers))]

    return [
        _line(headers, widths),
        "-+-".join("-" * size for size in widths),
        *(_line(row, widths) for row in values),
    ]


def _cells(rows: Rows, marks: Marks) -> tuple[list[str], list[list[str]]]:
    columns = list(dict.fromkeys(column for row in rows for column in row))
    headers = ["row", *(_escape(column) for column in columns)]
    values = [
        [
            str(index + 1),
            *(
                ("! " if (index, column) in marks else "")
                + (_value(row[column]) if column in row else "<missing>")
                for column in columns
            ),
        ]
        for index, row in enumerate(rows)
    ]
    return headers, values


def _panels(rows: Rows, marks: Marks, width: int) -> list[str]:
    headers, values = _cells(rows, marks)
    if len(headers) == 1:
        return [
            cell[0][start : start + width]
            for cell in [headers, *values]
            for start in range(0, len(cell[0]), width)
        ]
    natural = [max(len(row[i]) for row in [headers, *values]) for i in range(len(headers))]
    include_row = width >= natural[0] + 4
    available = width - natural[0] - 3 if include_row else width
    panels: list[list[int]] = []
    current: list[int] = []
    used = natural[0] if include_row else 0
    for column in range(1, len(headers)):
        size = min(natural[column], available)
        extra = size + (3 if current or include_row else 0)
        if current and used + extra > width:
            panels.append(current)
            current = []
            used = natural[0] if include_row else 0
            extra = size + (3 if include_row else 0)
        current.append(column)
        used += extra
    if current:
        panels.append(current)

    result: list[str] = []
    for panel in panels:
        if result:
            result.append("")
        indices = ([0] if include_row else []) + panel
        widths = [natural[0] if i == 0 else min(natural[i], available) for i in indices]
        for cells in [headers, *values]:
            chunks = [
                [cells[i][start : start + size] for start in range(0, len(cells[i]), size)] or [""]
                for i, size in zip(indices, widths, strict=True)
            ]
            for part in range(max(map(len, chunks))):
                result.append(
                    _line(
                        [
                            chunks[i][part] if part < len(chunks[i]) else ""
                            for i in range(len(chunks))
                        ],
                        widths,
                        trim=False,
                    )
                )
            if cells is headers:
                result.append("-+-".join("-" * size for size in widths))
    return result


def _line(cells: list[str], widths: list[int], *, trim: bool = True) -> str:
    line = " | ".join(cell.ljust(size) for cell, size in zip(cells, widths, strict=True))
    return line.rstrip() if trim else line


def _value(value: object) -> str:
    def encode(item: object) -> str:
        if isinstance(item, (datetime.date, datetime.datetime)):
            return item.isoformat()
        raise TypeError(f"Unsupported dataframe value: {type(item).__name__}")

    return json.dumps(value, ensure_ascii=True, default=encode)


def _escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)[1:-1]


def _print_wrapped(value: str, width: int) -> None:
    for line in textwrap.wrap(
        value, width=width, replace_whitespace=False, drop_whitespace=False, break_on_hyphens=False
    ):
        print(line)
