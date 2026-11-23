"""Optional analytical checks around explicit plan calls."""

import dataclasses
from collections import abc

from uptimely import plan
from uptimely.engine.dataframe import backend as backend_module
from uptimely.spec import arg_types
from uptimely.spec.model import profile as profile_module


@dataclasses.dataclass(frozen=True)
class ValidationContext:
    """Snapshots needed to check one call's result."""

    comparison: object | None = None
    merge_target: object | None = None
    merge_fragment: object | None = None


class InvocationValidator:
    """Check declared dataframe contracts without changing function calls."""

    def __init__(self, backend: backend_module.DataFrameBackend) -> None:
        """Create a validator for the selected dataframe backend."""
        self.backend = backend

    def before(
        self, invocation: plan.Invocation, arguments: abc.Mapping[str, object]
    ) -> ValidationContext:
        """Check inputs and capture any comparison frames before the call.

        Raises:
            ValueError: The contract is missing or the inputs violate it.
        """
        semantics = invocation.semantics
        if semantics is None:
            raise ValueError(f"Invocation {invocation.id} is missing analytical semantics")

        frames: dict[str, object] = {}
        dataframe_names = [
            name
            for name, argument_type in semantics.argument_types.items()
            if arg_types.is_dataframe(argument_type)
        ]
        for name in dataframe_names:
            if name not in arguments:
                continue
            value = arguments[name]
            if value is None and semantics.argument_types[name] == arg_types.OPTIONAL_DATAFRAME:
                continue
            if not self.backend.is_frame(value):
                raise ValueError(
                    f"Argument {name} of invocation {invocation.id} must be a dataframe"
                )
            frames[name] = value

        if semantics.input_features and dataframe_names:
            available = {
                column for frame in frames.values() for column in self.backend.column_names(frame)
            }
            missing = sorted(set(semantics.input_features) - available)
            if missing:
                raise ValueError(
                    f"Invocation {invocation.id} is missing input features: " + ", ".join(missing)
                )

        if semantics.role == profile_module.OperatorBindingRole.MERGE:
            return self._before_merge(invocation, arguments)

        scope = semantics.dataframe_input_scope
        comparison = None
        if scope in (
            profile_module.DataFrameInputScope.TARGET,
            profile_module.DataFrameInputScope.FOREIGN,
        ):
            if semantics.profile_id is None or len(frames) != 1:
                raise ValueError(
                    f"Invocation {invocation.id} requires one {scope} dataframe reference"
                )
            name, frame = next(iter(frames.items()))
            reference = invocation.arguments.get(name)
            prefixes = (
                f"{plan.Variable.DATASET}{semantics.profile_id}.",
                f"{plan.Variable.MERGE}{semantics.profile_id}.",
            )
            is_target = isinstance(reference, str) and reference.startswith(prefixes)
            if not isinstance(reference, str) or not reference.startswith(plan.Variable.PREFIXES):
                raise ValueError(f"Invocation {invocation.id} requires a named dataframe reference")
            if is_target != (scope == profile_module.DataFrameInputScope.TARGET):
                raise ValueError(
                    f"Invocation {invocation.id} requires a {scope} dataframe reference"
                )
            if is_target:
                comparison = self.backend.snapshot(frame)
                self._validate_frame(
                    comparison,
                    semantics.target_identifiers,
                    description=f"Input of invocation {invocation.id}",
                    semantics=semantics,
                )
                collisions = sorted(
                    set(semantics.output_features) & set(self.backend.column_names(comparison))
                )
                if collisions:
                    raise ValueError(
                        f"Invocation {invocation.id} cannot replace existing columns: "
                        + ", ".join(collisions)
                    )

        return ValidationContext(comparison=comparison)

    def _before_merge(
        self, invocation: plan.Invocation, arguments: abc.Mapping[str, object]
    ) -> ValidationContext:
        semantics = invocation.semantics
        assert semantics is not None
        if "dataset" not in arguments or "fragment" not in arguments:
            raise ValueError(f"Merge invocation {invocation.id} requires dataset and fragment")
        target, fragment = arguments["dataset"], arguments["fragment"]
        if target is not None and not self.backend.is_frame(target):
            raise ValueError(f"Merge dataset of invocation {invocation.id} must be a dataframe")
        if not self.backend.is_frame(fragment):
            raise ValueError(f"Merge fragment of invocation {invocation.id} must be a dataframe")
        target_snapshot = self.backend.snapshot(target) if target is not None else None
        fragment_snapshot = self.backend.snapshot(fragment)
        columns = set(self.backend.column_names(fragment_snapshot))
        keys = [
            name
            for name in dict.fromkeys([*semantics.target_identifiers, *semantics.fragment_keys])
            if name in columns
        ]
        identifiers = (
            semantics.target_identifiers
            if set(semantics.target_identifiers).issubset(columns)
            else keys
        )
        self._validate_frame(
            fragment_snapshot,
            identifiers,
            description=f"Fragment of invocation {invocation.id}",
            semantics=semantics,
        )
        if target_snapshot is not None:
            target_columns = set(self.backend.column_names(target_snapshot))
            collisions = sorted((columns - set(keys)) & target_columns)
            if collisions:
                raise ValueError(
                    "Fragment feature columns overlap the accumulated profile frame: "
                    + ", ".join(collisions)
                )
            self._validate_frame(
                target_snapshot,
                semantics.target_identifiers,
                description=f"Merge input of invocation {invocation.id}",
                semantics=semantics,
            )
        return ValidationContext(merge_target=target_snapshot, merge_fragment=fragment_snapshot)

    def after(self, invocation: plan.Invocation, value: object, context: ValidationContext) -> None:
        """Check the returned value before it is stored.

        Raises:
            ValueError: The result violates the analytical contract.
        """
        semantics = invocation.semantics
        assert semantics is not None
        if context.merge_fragment is not None:
            self._validate_merge_result(invocation, value, context)
            return
        if semantics.result == plan.InvocationResultKind.NONE:
            return
        if not self.backend.is_frame(value):
            raise ValueError(f"Result of invocation {invocation.id} must be a dataframe")
        comparison = context.comparison
        if comparison is not None:
            comparison, value = self.backend.collect_pair(comparison, value)
        columns = set(self.backend.column_names(value))
        if semantics.result == plan.InvocationResultKind.FRAGMENT:
            keys = [
                name
                for name in dict.fromkeys([*semantics.target_identifiers, *semantics.fragment_keys])
                if name in columns
            ]
            identifiers = (
                keys
                if semantics.fragment_dimensions == profile_module.FragmentDimensions.SUBSET
                and not set(semantics.target_identifiers).issubset(columns)
                else semantics.target_identifiers
            )
            self._validate_frame(
                value,
                identifiers,
                description=f"Fragment of invocation {invocation.id}",
                semantics=semantics,
            )
        else:
            self._validate_frame(
                value,
                semantics.target_identifiers,
                description=f"Result of invocation {invocation.id}",
                semantics=semantics,
            )
        missing = sorted(set(semantics.output_features) - columns)
        if missing:
            raise ValueError(
                f"Invocation {invocation.id} is missing output columns: " + ", ".join(missing)
            )
        self._validate_preservation(
            invocation,
            value,
            comparison,
            fragment=semantics.result == plan.InvocationResultKind.FRAGMENT,
        )

    def _validate_merge_result(
        self, invocation: plan.Invocation, value: object, context: ValidationContext
    ) -> None:
        semantics = invocation.semantics
        assert semantics is not None and context.merge_fragment is not None
        description = f"Merge result of invocation {invocation.id}"
        self._validate_frame(value, semantics.target_identifiers, description, semantics)
        expected = set(self.backend.column_names(context.merge_fragment))
        if context.merge_target is not None:
            expected.update(self.backend.column_names(context.merge_target))
        actual = set(self.backend.column_names(value))
        missing = sorted(expected - actual)
        if missing:
            raise ValueError(f"{description} is missing required columns: " + ", ".join(missing))
        unexpected = sorted(actual - expected)
        if unexpected:
            raise ValueError(f"{description} contains undeclared columns: " + ", ".join(unexpected))

    def _validate_frame(
        self,
        frame: object,
        identifiers: abc.Sequence[str],
        description: str,
        semantics: plan.InvocationSemantics,
    ) -> None:
        if not self.backend.is_frame(frame):
            raise ValueError(f"{description} must be a dataframe")
        columns = set(self.backend.column_names(frame))
        missing = sorted(set(identifiers) - columns)
        if missing:
            raise ValueError(f"{description} is missing identifier columns: " + ", ".join(missing))
        if identifiers:
            duplicated = self.backend.is_duplicated(self.backend.select(frame, identifiers))
        else:
            duplicated = self.backend.row_count(frame) > 1
        if duplicated:
            raise ValueError(f"{description} contains duplicate identifiers")
        self.backend.validate_types(
            frame,
            {name: kind for name, kind in self._column_types(semantics).items() if name in columns},
        )

    def _validate_preservation(
        self,
        invocation: plan.Invocation,
        value: object,
        comparison: object | None,
        *,
        fragment: bool = False,
    ) -> None:
        semantics = invocation.semantics
        assert semantics is not None
        required = (
            semantics.row_count_relation == profile_module.RowCountRelation.SAME
            or semantics.key_relation == profile_module.KeyRelation.IDENTICAL
            or semantics.row_order_relation == profile_module.RowOrderRelation.PRESERVE
            or (
                not fragment
                and semantics.existing_data_relation == profile_module.ExistingDataRelation.PRESERVE
            )
        )
        if not required:
            return
        if comparison is None:
            raise ValueError(f"Invocation {invocation.id} requires a target comparison dataframe")
        keys = semantics.target_identifiers
        if (
            semantics.row_count_relation == profile_module.RowCountRelation.SAME
            and self.backend.row_count(comparison) != self.backend.row_count(value)
        ):
            raise ValueError(f"Invocation {invocation.id} must preserve row count")
        if (
            semantics.key_relation == profile_module.KeyRelation.IDENTICAL
            and not self.backend.same_keys(comparison, value, keys)
        ):
            raise ValueError(f"Invocation {invocation.id} must preserve identifier keys")
        if (
            semantics.row_order_relation == profile_module.RowOrderRelation.PRESERVE
            and keys
            and not self.backend.same_data(comparison, value, keys)
        ):
            raise ValueError(f"Invocation {invocation.id} must preserve row order")
        if (
            not fragment
            and semantics.existing_data_relation == profile_module.ExistingDataRelation.PRESERVE
        ):
            existing = self.backend.column_names(comparison)
            missing = sorted(set(existing) - set(self.backend.column_names(value)))
            if missing:
                raise ValueError(
                    f"Invocation {invocation.id} must preserve existing columns: "
                    + ", ".join(missing)
                )
            sort_by = (
                ()
                if semantics.row_order_relation == profile_module.RowOrderRelation.PRESERVE
                else keys
            )
            if not self.backend.same_data(comparison, value, existing, sort_by=sort_by):
                raise ValueError(f"Invocation {invocation.id} must preserve existing data")

    @staticmethod
    def _column_types(semantics: plan.InvocationSemantics) -> dict[str, str]:
        return {
            **semantics.column_types,
            **{name: value for name, value in semantics.output_types.items() if value is not None},
        }
