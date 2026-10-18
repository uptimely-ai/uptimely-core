"""Ordered semantic validation for spec documents."""

from __future__ import annotations

from . import dimensions
from . import spec as spec_validation
from .errors import SpecError
from .prepared import validate_prepared

validate_dataset_ids = dimensions.validate_dataset_ids


validate_spec = spec_validation.validate_spec

__all__ = [
    "SpecError",
    "validate_spec",
    "validate_dataset_ids",
    "validate_prepared",
]
