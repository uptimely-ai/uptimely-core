"""Tests for parsing implementation docstrings into Explorer documentation."""

import inspect

from example.src import analytics, external_workflow

from uptimely.explorer.sections import spec as spec_section

NUMPY_DOCSTRING = """Return the ordered difference within each asset.

Extended body text.

Parameters
----------
dataset
    Dataset containing the readings.
order_by
    Column defining the ordering.

Returns
-------
Dataset with the difference appended.

Raises
------
ValueError
    If the ordering column is missing.

Examples
--------
>>> frame = make_frame()
>>> delta(frame, "ts").collect()["delta"].to_list()
[None, 1.5]
"""


def test_numpy_docstring_parses_into_documentation_sections() -> None:
    documentation = spec_section._parse_docstring(NUMPY_DOCSTRING)

    assert documentation is not None
    assert documentation["summary"] == "Return the ordered difference within each asset."
    assert documentation["body"] == "Extended body text."
    assert documentation["params"] == {
        "dataset": "Dataset containing the readings.",
        "order_by": "Column defining the ordering.",
    }
    assert documentation["returns"] == "Dataset with the difference appended."
    assert documentation["raises"] == [
        {"type": "ValueError", "description": "If the ordering column is missing."}
    ]
    assert documentation["examples"] == [
        'frame = make_frame()\ndelta(frame, "ts").collect()["delta"].to_list()\n[None, 1.5]'
    ]


def test_colon_suffixed_numpy_section_headers_are_normalized() -> None:
    hybrid = NUMPY_DOCSTRING.replace("Returns\n", "Returns:\n").replace("Raises\n", "Raises:\n")

    documentation = spec_section._parse_docstring(hybrid)

    assert documentation is not None
    assert documentation["returns"] == "Dataset with the difference appended."
    assert documentation["raises"][0]["type"] == "ValueError"


def test_summary_only_docstring_parses_without_sections() -> None:
    documentation = spec_section._parse_docstring("Only a summary line.")

    assert documentation is not None
    assert documentation["summary"] == "Only a summary line."
    assert documentation["params"] == {}
    assert documentation["returns"] is None
    assert documentation["raises"] == []
    assert documentation["examples"] == []


def test_numpy_multiline_doctest_remains_one_example() -> None:
    docstring = inspect.getdoc(analytics.operation_point_quantum_optimization)
    assert docstring is not None
    documentation = spec_section._parse_docstring(docstring)

    assert documentation is not None
    assert documentation["examples"] == [
        "frame = pl.LazyFrame(\n"
        '    {"pressure": [4.0], "flow": [10.0], "power": [5.0], "temp": [80.0], "vib": [3.0]}\n'
        ")\n"
        'features = ["pressure", "flow", "power", "temp", "vib"]\n'
        'result = operation_point_quantum_optimization(frame, features, "recommendation")\n'
        'result.collect()["recommendation"].to_list()[0]["converged"]\n'
        "True"
    ]


def test_numpy_examples_preserve_output_and_prose_between_prompts() -> None:
    docstring = """Summary.

Examples
--------
>>> x = 1
>>> x
1

Then add one.

>>> x + 1
2

Notes
-----
Not part of the example.
"""
    documentation = spec_section._parse_docstring(docstring)

    assert documentation is not None
    assert documentation["examples"] == ["x = 1\nx\n1\n\nThen add one.\n\nx + 1\n2"]


def test_google_example_and_legacy_numpy_headers_remain_supported() -> None:
    google = """Summary.

Args:
    x: Input value.

Example:
    >>> compute(1)
    2
"""
    documentation = spec_section._parse_docstring(google)
    assert documentation is not None
    assert documentation["params"] == {"x": "Input value."}
    assert documentation["examples"] == ["compute(1)\n2"]

    legacy = inspect.getdoc(analytics.read_pump_telemetry)
    assert legacy is not None
    legacy = legacy.replace("Examples\n", "Examples:\n")
    documentation = spec_section._parse_docstring(legacy)
    assert documentation is not None
    assert documentation["examples"] == [
        "telemetry = read_pump_telemetry(\n"
        '    "data/pump_telemetry.json",\n'
        '    "data/pump_assets.json",\n'
        '    production_line="line_1",\n'
        ")"
    ]


def test_example_function_docstrings_use_numpy_section_headers() -> None:
    for module in (analytics, external_workflow):
        for _, function in inspect.getmembers(module, inspect.isfunction):
            if function.__module__ != module.__name__:
                continue
            docstring = inspect.getdoc(function)
            assert docstring is not None
            for section in ("Parameters", "Returns", "Raises", "Examples"):
                assert f"\n{section}:\n" not in docstring, function.__name__
