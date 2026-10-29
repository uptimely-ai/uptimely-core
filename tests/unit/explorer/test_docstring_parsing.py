"""Tests for parsing implementation docstrings into Explorer documentation."""

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
        '>>> frame = make_frame()\n>>> delta(frame, "ts").collect()["delta"].to_list()\n[None, 1.5]'
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
