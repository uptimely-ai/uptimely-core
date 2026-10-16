"""Ordered semantic validation for analytics documents."""

from __future__ import annotations

from . import analytics as analytics_validation
from . import dimensions
from .errors import AnalyticsError
from .prepared import validate_prepared

validate_dataset_ids = dimensions.validate_dataset_ids


validate_analytics = analytics_validation.validate_analytics

__all__ = [
    "AnalyticsError",
    "validate_analytics",
    "validate_dataset_ids",
    "validate_prepared",
]
