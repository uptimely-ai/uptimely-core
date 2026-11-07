"""Per-execution state and lookups for portable plan execution."""

import dataclasses

from uptimely import plan as execution_plan
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.dataframe import main_frame as main_frame_module


@dataclasses.dataclass
class RuntimeState:
    """Main frames, retained fragments, and calculated outputs for one execution."""

    main_frames: dict[str, main_frame_module.MainFrame] = dataclasses.field(default_factory=dict)
    staged_fragments: dict[str, fragment_module.Fragment] = dataclasses.field(default_factory=dict)
    calculated_outputs: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)

    def staged_fragment_for(
        self, invocation: execution_plan.Invocation
    ) -> tuple[str, fragment_module.Fragment]:
        """Find the single staged fragment dependency of a merge invocation.

        Raises:
            ValueError: The invocation does not depend on exactly one staged fragment.
        """
        dependencies = [
            dependency_id
            for dependency_id in invocation.dependency_ids
            if dependency_id in self.staged_fragments
        ]
        if len(dependencies) != 1:
            raise ValueError(
                f"Merge invocation {invocation.id} requires exactly one staged fragment dependency"
            )
        dependency_id = dependencies[0]
        return dependency_id, self.staged_fragments[dependency_id]

    def resolve_main_frame_or_fragment_dataframe(self, identifier: str) -> object | None:
        """Resolve a main-frame dataset ID or fragment mapping ID to its dataframe.

        Main-frame IDs take precedence over fragment names.

        Args:
            identifier: Dataset ID or fragment mapping ID.

        Returns:
            The underlying dataframe, or None when neither kind of reference exists.

        Raises:
            ValueError: A fragment name matches multiple main frames.
        """
        main_frame = self.main_frames.get(identifier)
        if main_frame is not None:
            return main_frame.dataframe
        matches = [
            main.fragments[identifier].dataframe
            for main in self.main_frames.values()
            if identifier in main.fragments
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous fragment reference: {identifier}")
        return matches[0] if matches else None
