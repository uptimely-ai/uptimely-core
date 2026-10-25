"""Display execution plan stages in the CLI."""

import logging

from uptimely import execution_plan

logger = logging.getLogger(__name__)


def log_stages(plan: execution_plan.ExecutionPlan) -> None:
    """Log execution stages and their function dependencies."""
    invocations_by_id = plan.invocations_by_id
    logger.info("\nExecution stages")
    for stage_number, stage in enumerate(plan.execution_stages, 1):
        logger.info("Stage %d", stage_number)
        for invocation in stage:
            dependencies = [
                invocations_by_id[dependency_id].function_id
                for dependency_id in invocation.dependency_ids
            ]
            suffix = f" <- [{', '.join(dependencies)}]" if dependencies else ""
            logger.info(
                "  %s(%s) -> %s%s",
                invocation.function_id,
                invocation.entity_id,
                ", ".join(invocation.output_features) or invocation.mapping_id,
                suffix,
            )
