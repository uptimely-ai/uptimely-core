"""Prepare and validate physical dataframe assembly without publishing state."""

from __future__ import annotations

import functools
import logging
import typing
from collections import abc

from uptimely.library.merge import polars as merge_module

if typing.TYPE_CHECKING:
    from . import dataset as dataset_module
    from . import fragment as fragment_module

logger = logging.getLogger(__name__)


class Merge:
    """Own assembly checks and execution for a target dataset and staged fragment."""

    def __init__(self, dataset: dataset_module.Dataset, fragment: fragment_module.Fragment) -> None:
        """Create an assembly operation without changing the target dataset."""
        self.dataset = dataset
        self.fragment = fragment
        self.backend = dataset.backend

    def execute(
        self,
        load: abc.Callable[[], object] | None = None,
        *,
        description: str = "Merge result",
        column_types: abc.Mapping[str, str] | None = None,
        validate: bool = False,
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> object:
        """Assemble and validate a candidate frame without publishing it.

        Args:
            load: Configured merge invocation; omitted for automatic key-based assembly.
            description: Identity used in validation logs and errors.
            column_types: Logical types of known target columns.
            validate: Whether to check content in addition to structure and collisions.
            join_cardinality: Full-join cardinality for automatic assembly.
            broadcast_cardinality: Left-join cardinality for automatic assembly.

        Returns:
            The complete validated candidate dataframe.

        Raises:
            ValueError: Inputs collide or the result violates its dataframe contract.
        """
        self.validate_input(column_types=column_types, validate=validate)
        if load is None:
            load = functools.partial(
                merge_module.merge_by_grain,
                self.dataset.dataframe,
                self.fragment.dataframe,
                self.dataset.id_columns,
                identifier_columns=self.fragment.identifiers,
                join_cardinality=join_cardinality,
                broadcast_cardinality=broadcast_cardinality,
            )
        result = load()
        self.validate_result(
            result, description=description, column_types=column_types, validate=validate
        )
        return result

    def validate_input(
        self,
        *,
        column_types: abc.Mapping[str, str] | None = None,
        validate: bool = False,
    ) -> None:
        """Reject overlapping features and optionally validate the current target."""
        if self.dataset.dataframe is None:
            return
        logger.debug("Check fragment feature collisions")
        fragment_columns = set(self.backend.column_names(self.fragment.dataframe))
        existing_columns = set(self.backend.column_names(self.dataset.dataframe))
        collisions = sorted((fragment_columns - set(self.fragment.identifiers)) & existing_columns)
        if collisions:
            raise ValueError(
                "Fragment feature columns overlap the accumulated profile frame: "
                + ", ".join(collisions)
            )
        if validate:
            self.dataset.validate_accumulated_frame(column_types=column_types)

    def validate_result(
        self,
        result: object,
        *,
        description: str = "Merge result",
        column_types: abc.Mapping[str, str] | None = None,
        validate: bool = False,
    ) -> None:
        """Require exactly the target and fragment columns before publication."""
        self.dataset.validate_frame(result, description=description)
        expected_columns = set(self.backend.column_names(self.fragment.dataframe))
        if self.dataset.dataframe is not None:
            expected_columns.update(self.backend.column_names(self.dataset.dataframe))
        logger.debug(
            "Check merge result contains exactly columns %s for %s",
            sorted(expected_columns),
            description,
        )
        actual_columns = set(self.backend.column_names(result))
        missing = sorted(expected_columns - actual_columns)
        if missing:
            raise ValueError(f"{description} is missing required columns: " + ", ".join(missing))
        unexpected = sorted(actual_columns - expected_columns)
        if unexpected:
            raise ValueError(f"{description} contains undeclared columns: " + ", ".join(unexpected))
        if validate:
            self.dataset.validate_frame(
                result, description=description, column_types=column_types, validate_content=True
            )
