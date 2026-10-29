"""Public semantic-validation entry points.

Atomic rules accept a spec and raise on failure. The runner orders their prerequisites.
"""

from __future__ import annotations

from .errors import SpecError
from .rules.dataset import validate_dataset_ids
from .spec import validate_spec

__all__ = [
    "SpecError",
    "validate_spec",
    "validate_dataset_ids",
]
