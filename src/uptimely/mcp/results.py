"""Present engine results as bounded analytical tool responses."""

import polars as pl

from uptimely import engine, project


class ExecutionResponse:
    """Format existing engine previews without executing or collecting data."""

    @classmethod
    def format(
        cls,
        bundle: project.BuildBundle,
        result: engine.ExecutionResult,
        operator: tuple[str, str] | None = None,
    ) -> dict[str, object]:
        """Describe requested outputs and explicitly report unavailable results.

        Args:
            bundle: Saved build used for execution and output declarations.
            result: Engine result containing already collected previews.
            operator: Selected profile and operator, or None for the full build.

        Returns:
            Status, bounded datasets, and any execution or presentation failures.

        Raises:
            TypeError: An output has no valid preview without an engine failure.
        """
        outputs = cls._outputs(bundle, result, operator)
        preview_failures = {
            profile_id: error
            for profile_id, error in result.preview_failures.items()
            if profile_id in outputs
        }
        datasets, output_failures = cls._datasets(bundle, result, outputs, preview_failures)
        succeeded = cls._succeeded(bundle, result, operator)
        status = "ok" if succeeded and not (preview_failures or output_failures) else "failed"
        payload: dict[str, object] = {"status": status, "datasets": datasets}
        if operator is not None:
            payload["target"] = {"profile": operator[0], "operator": operator[1]}
        if result.failures:
            payload["warnings" if status == "ok" else "failures"] = result.failures
        if preview_failures:
            payload["preview_failures"] = preview_failures
        if output_failures:
            payload["output_failures"] = output_failures
        return payload

    @staticmethod
    def _outputs(
        bundle: project.BuildBundle,
        result: engine.ExecutionResult,
        operator: tuple[str, str] | None,
    ) -> dict[str, list[str]]:
        """Group returned features by profile in stable order."""
        if operator is not None:
            profile_id, operator_id = operator
            features = (
                bundle.spec_definition.profiles[profile_id].assembly[operator_id].output_features
            )
            return {profile_id: sorted(features)} if features else {}
        outputs: dict[str, list[str]] = {}
        for profile_id, feature_id in sorted(result.calculated_outputs):
            outputs.setdefault(profile_id, []).append(feature_id)
        return outputs

    @staticmethod
    def _succeeded(
        bundle: project.BuildBundle,
        result: engine.ExecutionResult,
        operator: tuple[str, str] | None,
    ) -> bool:
        """Preserve full-build warning policy and stricter targeted-run status."""
        if operator is not None:
            return not result.failures
        producers = bundle.spec_definition.calculated_feature_producers
        expected = {(profile_id, feature) for feature, (profile_id, _) in producers.items()}
        return expected <= result.calculated_outputs.keys() and (
            bool(expected) or not result.failures
        )

    @staticmethod
    def _datasets(
        bundle: project.BuildBundle,
        result: engine.ExecutionResult,
        outputs: dict[str, list[str]],
        preview_failures: dict[str, str],
    ) -> tuple[list[dict[str, object]], dict[str, str]]:
        """Project collected previews onto identifiers and requested features."""
        datasets: list[dict[str, object]] = []
        failures: dict[str, str] = {}
        definition = bundle.spec_definition
        for profile_id, features in sorted(outputs.items()):
            if profile_id in preview_failures:
                continue
            frame = result.preview_frames.get(profile_id)
            if frame is None and result.failures:
                continue
            if not isinstance(frame, pl.DataFrame):
                raise TypeError(
                    f"Execution produced outputs for profile {profile_id} "
                    "without a serializable dataset preview"
                )
            profile_key = definition.profile_keys[profile_id]
            identifiers = definition.identifiers_by_profile[profile_key]
            columns = list(dict.fromkeys([*identifiers, *features]))
            missing = sorted(set(columns) - set(frame.columns))
            if missing:
                failures[profile_id] = (
                    "Requested output columns were not published: "
                    + ", ".join(missing)
                    + ". Functions that only write results internally must expose "
                    "a dataframe result through their operator to return analytical rows."
                )
                continue
            rows = frame.select(columns).to_dicts()
            datasets.append(
                {
                    "profile": profile_id,
                    "features": features,
                    "columns": columns,
                    "row_count": len(rows),
                    "rows": rows,
                }
            )
        return datasets, failures
