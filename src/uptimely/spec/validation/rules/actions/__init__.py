"""Action declarations and read-only iteration for atomic action rules."""

from __future__ import annotations

import collections.abc
import dataclasses

from uptimely.spec import functions, references, selectors
from uptimely.spec import model as spec_model
from uptimely.spec.validation import errors
from uptimely.spec.validation.rules import datasets


@dataclasses.dataclass(frozen=True)
class ActionDeclaration:
    """A declared action with its dataset, function, references, and spec paths."""

    dataset_declaration: datasets.DatasetDeclaration
    action_id: str
    action: spec_model.Action
    function: spec_model.FunctionTemplate | None

    @property
    def dataset(self) -> spec_model.Dataset:
        """Return the declared dataset."""
        return self.dataset_declaration.dataset

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the declaration identity."""
        return (*self.dataset_declaration.key, self.action_id)

    @property
    def path(self) -> errors.SpecPath:
        """Return the model-ID path used by action contracts."""
        return (*self.dataset_declaration.path, "actions", self.action.id)

    @property
    def declaration_path(self) -> errors.SpecPath:
        """Return the dictionary-key path used by bindings."""
        return (*self.path[:-1], self.action_id)

    @property
    def inputs(self) -> tuple[str, ...]:
        """Return explicit input dependencies, not binding selectors."""
        return tuple(self.action.input_features)

    @property
    def outputs(self) -> tuple[str, ...]:
        """Return declared outputs."""
        return tuple(self.action.output_features)

    @property
    def feature_selectors(self) -> tuple[str, ...]:
        """Return structural feature references in binding arguments."""
        return tuple(
            references.structural_references(self.action.binding.args, selectors.FEATURE_PREFIX)
        )

    @property
    def dataset_references(self) -> tuple[str, ...]:
        """Return structural dataset references in binding arguments."""
        return tuple(
            references.structural_references(self.action.binding.args, selectors.DATASET_PREFIX)
        )

    @property
    def dimension_references(self) -> tuple[str, ...]:
        """Return structural dimension references in binding arguments."""
        return tuple(dimension for dimension, _ in self.dimension_reference_paths)

    @property
    def dimension_reference_paths(self) -> tuple[tuple[str, errors.SpecPath], ...]:
        """Return dimension references with their declaration paths."""
        return tuple(
            references.structural_reference_paths(
                self.action.binding.args,
                selectors.DIMENSION_PREFIX,
                (*self.declaration_path, "binding", "args"),
            )
        )

    @property
    def dimensions(self) -> frozenset[str]:
        """Return the dimensions declared by this action's entity."""
        return self.dataset_declaration.dimensions

    @property
    def local_features(self) -> frozenset[str]:
        """Return the dataset's features together with its entity dimensions."""
        return frozenset(self.dataset.features) | self.dimensions

    @property
    def kind(self) -> functions.FunctionKind | None:
        """Return the declared kind without requiring function resolution."""
        return self.function.kind if self.function is not None else None


def iter_actions(spec: spec_model.Spec) -> collections.abc.Iterator[ActionDeclaration]:
    """Yield action declarations and structural references without validating them."""
    for location in datasets.iter_datasets(spec):
        for action_id, action in location.dataset.actions.items():
            yield ActionDeclaration(
                dataset_declaration=location,
                action_id=action_id,
                action=action,
                function=spec.functions.root.get(action.binding.function),
            )
