"""Display execution plan stages in the CLI."""

import logging

from uptimely import execution_plan

logger = logging.getLogger(__name__)


def log_stages(plan: execution_plan.ExecutionPlan) -> None:
    """Log execution stages and their function dependencies."""
    callables_by_id = {callable.id: callable for callable in plan.callables}
    logger.info("\nExecution stages")
    for stage_number, stage in enumerate(plan.execution_stages, 1):
        logger.info("Stage %d", stage_number)
        for callable in stage:
            dependencies = [
                callables_by_id[dependency_id].function_id
                for dependency_id in callable.dependency_ids
            ]
            suffix = f" <- [{', '.join(dependencies)}]" if dependencies else ""
            logger.info(
                "  %s(%s) -> %s%s",
                callable.function_id,
                callable.entity_id,
                callable.output,
                suffix,
            )
