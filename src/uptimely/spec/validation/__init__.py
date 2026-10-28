"""Public semantic-validation entry points.

The spec coordinator orders read-only domain checks over context-prepared facts.
"""

from __future__ import annotations

from .dataset import validate_dataset_ids
from .errors import SpecError
from .spec import validate_spec

__all__ = [
    "SpecError",
    "validate_spec",
    "validate_dataset_ids",
]
