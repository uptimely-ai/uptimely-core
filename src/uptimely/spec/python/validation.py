"""Validation rules for Python-friendly spec declarations."""

from __future__ import annotations

from collections import abc

from . import ref


def validate_action_output_references(
    action_id: str,
    references: abc.Iterable[ref.Reference],
    output_ids: abc.Iterable[str],
) -> None:
    """Require every action output reference to name a declared output."""
    declared_outputs = set(output_ids)
    for reference in references:
        if isinstance(reference, ref.OutputReference) and reference.name not in declared_outputs:
            raise ValueError(
                f"Action '{action_id}' references undeclared output '{reference.name}'"
            )
