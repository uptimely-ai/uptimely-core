"""Public semantic-validation entry points.

The spec coordinator orders domain phases and their intermediate artifacts.
Resource traversal, resolution, and invariant checks remain in domain modules.
"""

from __future__ import annotations

from . import dataset as dataset_validation
from . import spec as spec_validation
from .errors import SpecError

validate_spec = spec_validation.validate_spec
validate_dataset_ids = dataset_validation.validate_dataset_ids

__all__ = [
    "SpecError",
    "validate_spec",
    "validate_dataset_ids",
]
